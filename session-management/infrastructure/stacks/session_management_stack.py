"""
CDK Stack for Session Management Infrastructure.
"""
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    Size,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigatewayv2 as apigwv2,
    aws_logs as logs,
    aws_iam as iam,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_events as events,
    aws_events_targets as targets,
    aws_cognito as cognito,
    aws_s3 as s3,
)
from constructs import Construct


class SessionManagementStack(Stack):
    """
    CDK Stack for Session Management and WebSocket Infrastructure.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: dict,
        env_name: str,
        audio_transcription_stack=None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.config = config
        self.env_name = env_name
        self.audio_transcription_stack = audio_transcription_stack

        # Import existing Cognito User Pool
        self.user_pool = self._import_user_pool()

        # Create DynamoDB tables
        self.sessions_table = self._create_sessions_table()
        self.connections_table = self._create_connections_table()
        self.rate_limits_table = self._create_rate_limits_table()

        # Create S3 bucket for audio chunks (Phase 2)
        self.audio_chunks_bucket = self._create_audio_chunks_bucket()

        # Create shared Lambda layer
        self.shared_layer = self._create_shared_layer()

        # Create Lambda functions
        self.authorizer_function = self._create_authorizer_function()
        self.connection_handler = self._create_connection_handler()
        self.heartbeat_handler = self._create_heartbeat_handler()
        self.disconnect_handler = self._create_disconnect_handler()
        self.refresh_handler = self._create_refresh_handler()
        self.session_status_handler = self._create_session_status_handler()
        
        # Create KVS Stream Writer Lambda (Phase 2)
        self.kvs_stream_writer = self._create_kvs_stream_writer()
        
        # Create FFmpeg Lambda Layer (Phase 3)
        self.ffmpeg_layer = self._create_ffmpeg_layer()
        
        # Create S3 Audio Consumer Lambda (Phase 3)
        self.s3_audio_consumer = self._create_s3_audio_consumer()
        
        # Create KVS Stream Consumer Lambda (Phase 3)
        self.kvs_stream_consumer = self._create_kvs_stream_consumer()

        # Grant connection_handler permission to invoke kvs_stream_writer (Phase 2)
        self.kvs_stream_writer.grant_invoke(self.connection_handler)
        self.connection_handler.add_environment(
            "KVS_STREAM_WRITER_FUNCTION",
            self.kvs_stream_writer.function_name
        )

        # Create WebSocket API
        self.websocket_api = self._create_websocket_api()

        # Create EventBridge rule for periodic status updates
        self._create_periodic_status_update_rule()
        
        # Create EventBridge rules for KVS stream processing (Phase 3)
        self._create_kvs_event_rules()

        # Create SNS topic for alarms
        self.alarm_topic = self._create_alarm_topic()

        # Create CloudWatch alarms
        self._create_cloudwatch_alarms()

        # Outputs
        self._create_outputs()

    def _import_user_pool(self) -> cognito.UserPool:
        """Import existing Cognito User Pool."""
        user_pool = cognito.UserPool.from_user_pool_id(
            self,
            'UserPool',
            user_pool_id=self.config.get('cognitoUserPoolId', ''),
        )
        return user_pool

    def _create_sessions_table(self) -> dynamodb.Table:
        """Create Sessions DynamoDB table."""
        table = dynamodb.Table(
            self,
            "SessionsTable",
            table_name=f"Sessions-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="sessionId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expiresAt",
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
        )
        return table

    def _create_connections_table(self) -> dynamodb.Table:
        """Create Connections DynamoDB table with GSI."""
        table = dynamodb.Table(
            self,
            "ConnectionsTable",
            table_name=f"Connections-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="connectionId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
        )

        # Add GSI for querying by sessionId and targetLanguage
        table.add_global_secondary_index(
            index_name="sessionId-targetLanguage-index",
            partition_key=dynamodb.Attribute(
                name="sessionId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="targetLanguage",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        return table

    def _create_rate_limits_table(self) -> dynamodb.Table:
        """Create RateLimits DynamoDB table."""
        table = dynamodb.Table(
            self,
            "RateLimitsTable",
            table_name=f"RateLimits-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="identifier",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expiresAt",
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
        )
        return table

    def _create_audio_chunks_bucket(self) -> s3.Bucket:
        """Create S3 bucket for storing audio chunks."""
        bucket = s3.Bucket(
            self,
            "AudioChunksBucket",
            bucket_name=f"low-latency-audio-{self.env_name}",
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            auto_delete_objects=True if self.env_name == "dev" else False,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldChunks",
                    expiration=Duration.days(1),  # Auto-delete after 1 day
                    enabled=True,
                )
            ],
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=False,
        )
        return bucket

    def _create_shared_layer(self) -> lambda_.LayerVersion:
        """Create Lambda Layer with shared code.
        
        Lambda Layers require a specific directory structure:
        lambda_layer/python/shared/  <- shared code goes here
        """
        layer = lambda_.LayerVersion(
            self,
            "SharedLayer",
            layer_version_name=f"session-management-shared-{self.env_name}",
            code=lambda_.Code.from_asset("../lambda_layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="Shared libraries for session management (repositories, services, utils)",
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
        )
        return layer

    def _create_authorizer_function(self) -> lambda_.Function:
        """Create Lambda Authorizer function with cryptography library."""
        # Get log retention from config (12 hours not available in CDK, using ONE_DAY)
        log_retention_hours = int(self.config.get("dataRetentionHours", 12))
        log_retention = logs.RetentionDays.ONE_DAY  # CDK doesn't support TWELVE_HOURS
        
        function = lambda_.Function(
            self,
            "AuthorizerFunction",
            function_name=f"session-authorizer-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/authorizer"),
            layers=[self.shared_layer],
            timeout=Duration.seconds(10),
            environment={
                "ENV": self.env_name,
                "REGION": self.config.get("region", "us-east-1"),
                "USER_POOL_ID": self.config.get("cognitoUserPoolId", ""),
                "CLIENT_ID": self.config.get("cognitoClientId", ""),
            },
            log_retention=log_retention,
        )
        return function

    def _create_connection_handler(self) -> lambda_.Function:
        """Create Connection Handler function."""
        # Get log retention from config (12 hours not available in CDK, using ONE_DAY)
        log_retention_hours = int(self.config.get("dataRetentionHours", 12))
        log_retention = logs.RetentionDays.ONE_DAY  # CDK doesn't support TWELVE_HOURS
        
        function = lambda_.Function(
            self,
            "ConnectionHandler",
            function_name=f"session-connection-handler-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/connection_handler"),
            layers=[self.shared_layer],
            timeout=Duration.seconds(30),
            environment={
                "ENV": self.env_name,
                "SESSIONS_TABLE": self.sessions_table.table_name,
                "CONNECTIONS_TABLE": self.connections_table.table_name,
                "RATE_LIMITS_TABLE": self.rate_limits_table.table_name,
                "SESSION_MAX_DURATION_HOURS": str(self.config.get("sessionMaxDurationHours", 2)),
                "MAX_LISTENERS_PER_SESSION": str(self.config.get("maxListenersPerSession", 500)),
                # API_GATEWAY_ENDPOINT will be added after WebSocket API is created
            },
            log_retention=log_retention,
        )

        # Grant DynamoDB permissions
        self.sessions_table.grant_read_write_data(function)
        self.connections_table.grant_read_write_data(function)
        self.rate_limits_table.grant_read_write_data(function)

        # Grant CloudWatch Metrics permissions
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=['cloudwatch:PutMetricData'],
                resources=['*']
            )
        )

        return function

    def _create_heartbeat_handler(self) -> lambda_.Function:
        """Create Heartbeat Handler function."""
        # Get log retention from config (12 hours not available in CDK, using ONE_DAY)
        log_retention_hours = int(self.config.get("dataRetentionHours", 12))
        log_retention = logs.RetentionDays.ONE_DAY  # CDK doesn't support TWELVE_HOURS
        
        function = lambda_.Function(
            self,
            "HeartbeatHandler",
            function_name=f"session-heartbeat-handler-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/heartbeat_handler"),
            layers=[self.shared_layer],
            timeout=Duration.seconds(10),
            environment={
                "ENV": self.env_name,
                "CONNECTIONS_TABLE": self.connections_table.table_name,
                "CONNECTION_REFRESH_MINUTES": str(self.config.get("connectionRefreshMinutes", 100)),
                "CONNECTION_WARNING_MINUTES": str(self.config.get("connectionWarningMinutes", 105)),
            },
            log_retention=log_retention,
        )

        # Grant DynamoDB permissions
        self.connections_table.grant_read_data(function)

        return function

    def _create_disconnect_handler(self) -> lambda_.Function:
        """Create Disconnect Handler function."""
        # Get log retention from config (12 hours not available in CDK, using ONE_DAY)
        log_retention_hours = int(self.config.get("dataRetentionHours", 12))
        log_retention = logs.RetentionDays.ONE_DAY  # CDK doesn't support TWELVE_HOURS
        
        function = lambda_.Function(
            self,
            "DisconnectHandler",
            function_name=f"session-disconnect-handler-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/disconnect_handler"),
            layers=[self.shared_layer],
            timeout=Duration.seconds(30),
            environment={
                "ENV": self.env_name,
                "SESSIONS_TABLE": self.sessions_table.table_name,
                "CONNECTIONS_TABLE": self.connections_table.table_name,
            },
            log_retention=log_retention,
        )

        # Grant DynamoDB permissions
        self.sessions_table.grant_read_write_data(function)
        self.connections_table.grant_read_write_data(function)

        return function

    def _create_refresh_handler(self) -> lambda_.Function:
        """Create Connection Refresh Handler function."""
        # Get log retention from config (12 hours not available in CDK, using ONE_DAY)
        log_retention_hours = int(self.config.get("dataRetentionHours", 12))
        log_retention = logs.RetentionDays.ONE_DAY  # CDK doesn't support TWELVE_HOURS
        
        function = lambda_.Function(
            self,
            "RefreshHandler",
            function_name=f"session-refresh-handler-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/refresh_handler"),
            layers=[self.shared_layer],
            timeout=Duration.seconds(30),
            environment={
                "ENV": self.env_name,
                "SESSIONS_TABLE": self.sessions_table.table_name,
                "CONNECTIONS_TABLE": self.connections_table.table_name,
                "SESSION_MAX_DURATION_HOURS": str(self.config.get("sessionMaxDurationHours", 2)),
                # JWT validation (application-level since WebSocket custom routes don't support authorizers)
                "REGION": self.config.get("region", "us-east-1"),
                "USER_POOL_ID": self.config.get("cognitoUserPoolId", ""),
                "CLIENT_ID": self.config.get("cognitoClientId", ""),
            },
            log_retention=log_retention,
        )

        # Grant DynamoDB permissions
        self.sessions_table.grant_read_write_data(function)
        self.connections_table.grant_read_write_data(function)

        return function

    def _create_session_status_handler(self) -> lambda_.Function:
        """Create Session Status Handler function."""
        # Get log retention from config (12 hours not available in CDK, using ONE_DAY)
        log_retention_hours = int(self.config.get("dataRetentionHours", 12))
        log_retention = logs.RetentionDays.ONE_DAY  # CDK doesn't support TWELVE_HOURS
        
        function = lambda_.Function(
            self,
            "SessionStatusHandler",
            function_name=f"session-status-handler-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/session_status_handler"),
            layers=[self.shared_layer],
            timeout=Duration.seconds(5),
            environment={
                "ENV": self.env_name,
                "SESSIONS_TABLE": self.sessions_table.table_name,
                "CONNECTIONS_TABLE": self.connections_table.table_name,
                "STATUS_QUERY_TIMEOUT_MS": "500",
                "PERIODIC_UPDATE_INTERVAL_SECONDS": "30",
                "LISTENER_COUNT_CHANGE_THRESHOLD_PERCENT": "10",
            },
            log_retention=log_retention,
        )

        # Grant DynamoDB permissions
        self.sessions_table.grant_read_data(function)
        self.connections_table.grant_read_data(function)

        return function

    def _create_kvs_stream_writer(self) -> lambda_.Function:
        """Create KVS Stream Writer Lambda function (Phase 2) - S3 storage."""
        # Get log retention from config
        log_retention_hours = int(self.config.get("dataRetentionHours", 12))
        log_retention = logs.RetentionDays.ONE_DAY
        
        function = lambda_.Function(
            self,
            "KVSStreamWriter",
            function_name=f"kvs-stream-writer-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/kvs_stream_writer"),
            layers=[self.shared_layer],
            timeout=Duration.seconds(10),
            memory_size=256,  # Reduced - no conversion needed
            environment={
                "STAGE": self.env_name,
                "SESSIONS_TABLE_NAME": self.sessions_table.table_name,
            },
            log_retention=log_retention,
            description="Receives WebM chunks and writes to S3",
        )

        # Grant DynamoDB read access (for session metadata)
        self.sessions_table.grant_read_data(function)

        # Grant S3 write permissions
        self.audio_chunks_bucket.grant_write(function)

        # Grant CloudWatch permissions for metrics
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=['cloudwatch:PutMetricData'],
                resources=['*']
            )
        )

        return function

    def _create_ffmpeg_layer(self) -> lambda_.LayerVersion:
        """Create FFmpeg Lambda Layer for audio processing."""
        layer = lambda_.LayerVersion(
            self,
            "FFmpegLayer",
            layer_version_name=f"ffmpeg-layer-{self.env_name}",
            code=lambda_.Code.from_asset("../lambda_layers/ffmpeg"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="FFmpeg binary for audio conversion",
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
        )
        return layer

    def _create_s3_audio_consumer(self) -> lambda_.Function:
        """Create S3 Audio Consumer Lambda function (Phase 3)."""
        # Get log retention from config
        log_retention_hours = int(self.config.get("dataRetentionHours", 12))
        log_retention = logs.RetentionDays.ONE_DAY
        
        # Get audio processor function name
        audio_processor_function_name = "audio-processor-dev"
        if self.audio_transcription_stack:
            audio_processor_function_name = self.audio_transcription_stack.audio_processor_function.function_name
        
        function = lambda_.Function(
            self,
            "S3AudioConsumer",
            function_name=f"s3-audio-consumer-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/s3_audio_consumer"),
            layers=[self.shared_layer, self.ffmpeg_layer],
            timeout=Duration.seconds(60),  # 60 seconds for batch processing
            memory_size=1024,  # Higher memory for ffmpeg
            ephemeral_storage_size=Size.mebibytes(2048),  # 2GB for temporary audio files
            environment={
                "STAGE": self.env_name,
                "AUDIO_BUCKET_NAME": self.audio_chunks_bucket.bucket_name,
                "AUDIO_PROCESSOR_FUNCTION": audio_processor_function_name,
                "SESSIONS_TABLE_NAME": self.sessions_table.table_name,
                "BATCH_WINDOW_SECONDS": "3",  # Aggregate 3 seconds
                "MIN_CHUNKS_FOR_PROCESSING": "8",  # Minimum 2 seconds
            },
            log_retention=log_retention,
            description="Aggregates S3 audio chunks and converts to PCM",
        )

        # Grant S3 read permissions
        self.audio_chunks_bucket.grant_read(function)

        # Grant DynamoDB read access
        self.sessions_table.grant_read_data(function)

        # Grant Lambda invoke permissions for audio processor
        function.add_to_role_policy(
            iam.PolicyStatement(
                sid="InvokeAudioProcessor",
                actions=["lambda:InvokeFunction"],
                resources=[
                    f"arn:aws:lambda:{self.region}:{self.account}:function:{audio_processor_function_name}*"
                ],
            )
        )

        # Grant CloudWatch permissions for metrics
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=['cloudwatch:PutMetricData'],
                resources=['*']
            )
        )

        # Configure S3 event notification to trigger this function
        # Support both PCM (new) and WebM (legacy) formats
        from aws_cdk.aws_s3_notifications import LambdaDestination
        
        # Notification for PCM files (primary)
        self.audio_chunks_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            LambdaDestination(function),
            s3.NotificationKeyFilter(
                prefix="sessions/",
                suffix=".pcm"
            )
        )
        
        # Notification for WebM files (legacy support)
        self.audio_chunks_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            LambdaDestination(function),
            s3.NotificationKeyFilter(
                prefix="sessions/",
                suffix=".webm"
            )
        )

        return function

    def _create_websocket_api(self) -> apigwv2.CfnApi:
        """Create WebSocket API Gateway with routes."""
        # Create WebSocket API
        api = apigwv2.CfnApi(
            self,
            "WebSocketAPI",
            name=f"session-websocket-api-{self.env_name}",
            protocol_type="WEBSOCKET",
            route_selection_expression="$request.body.action",
        )

        # Create Lambda Authorizer for WebSocket API
        # CRITICAL: For REQUEST authorizers on WebSocket APIs, identity_source determines
        # when the authorizer is invoked. If specified (e.g., "route.request.querystring.token"),
        # the authorizer is ONLY invoked when that parameter is present.
        # To make the authorizer ALWAYS invoke (for both speakers with tokens and listeners without),
        # we must NOT specify identity_source, or set it to an empty list.
        authorizer = apigwv2.CfnAuthorizer(
            self,
            "WebSocketAuthorizer",
            api_id=api.ref,
            name=f"session-authorizer-{self.env_name}",
            authorizer_type="REQUEST",
            authorizer_uri=f"arn:aws:apigateway:{self.region}:lambda:path/2015-03-31/functions/{self.authorizer_function.function_arn}/invocations",
            # identity_source removed - authorizer will ALWAYS be invoked
        )

        # Grant API Gateway permission to invoke authorizer
        self.authorizer_function.add_permission(
            "AuthorizerInvokePermission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=f"arn:aws:execute-api:{self.region}:{self.account}:{api.ref}/*",
        )

        # Create Lambda integrations for existing handlers
        connect_integration = self._create_lambda_integration(api, self.connection_handler, "ConnectIntegration")
        disconnect_integration = self._create_lambda_integration(api, self.disconnect_handler, "DisconnectIntegration")
        heartbeat_integration = self._create_lambda_integration(api, self.heartbeat_handler, "HeartbeatIntegration")
        refresh_integration = self._create_lambda_integration(api, self.refresh_handler, "RefreshIntegration")
        
        # Create Lambda integrations for new audio/control routes
        # Add sendAudio route if audio_transcription_stack is provided
        if self.audio_transcription_stack:
            send_audio_integration = self._create_lambda_integration(
                api,
                self.audio_transcription_stack.audio_processor_function,
                "SendAudioIntegration",
                timeout_ms=60000  # 60 seconds for audio processing
            )
            # Configure binary frame support
            send_audio_integration.content_handling_strategy = "CONVERT_TO_BINARY"

        # Update Lambda environment with API Gateway endpoint (will be set after deployment)
        # This is a placeholder - actual endpoint will be available after deployment
        api_endpoint = f"https://{api.ref}.execute-api.{self.region}.amazonaws.com/prod"
        
        # Update handlers with API endpoint
        self.heartbeat_handler.add_environment("API_GATEWAY_ENDPOINT", api_endpoint)
        self.refresh_handler.add_environment("API_GATEWAY_ENDPOINT", api_endpoint)
        self.disconnect_handler.add_environment("API_GATEWAY_ENDPOINT", api_endpoint)
        self.connection_handler.add_environment("API_GATEWAY_ENDPOINT", api_endpoint)

        # Grant API Gateway Management API permissions
        # connection_handler needs this for sending control messages to listeners
        for function in [self.heartbeat_handler, self.refresh_handler, self.disconnect_handler, self.connection_handler]:
            function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["execute-api:ManageConnections", "execute-api:Invoke"],
                    resources=[f"arn:aws:execute-api:{self.region}:{self.account}:{api.ref}/*"],
                )
            )

        # Create $connect route WITH authorizer
        # The authorizer handles both speakers (with JWT) and listeners (without JWT)
        # - Speakers: JWT validated, userId extracted to context
        # - Listeners: No JWT required, empty userId in context
        # The connection_handler uses authorizer context to determine role
        connect_route = apigwv2.CfnRoute(
            self,
            "ConnectRoute",
            api_id=api.ref,
            route_key="$connect",
            authorization_type="CUSTOM",
            authorizer_id=authorizer.ref,
            target=f"integrations/{connect_integration.ref}",
        )

        # Create $disconnect route
        disconnect_route = apigwv2.CfnRoute(
            self,
            "DisconnectRoute",
            api_id=api.ref,
            route_key="$disconnect",
            target=f"integrations/{disconnect_integration.ref}",
        )

        # Create createSession route (for speakers)
        create_session_route = apigwv2.CfnRoute(
            self,
            "CreateSessionRoute",
            api_id=api.ref,
            route_key="createSession",
            target=f"integrations/{connect_integration.ref}",
        )
        
        # Create joinSession route (for listeners)
        join_session_route = apigwv2.CfnRoute(
            self,
            "JoinSessionRoute",
            api_id=api.ref,
            route_key="joinSession",
            target=f"integrations/{connect_integration.ref}",
        )

        # Create heartbeat custom route
        heartbeat_route = apigwv2.CfnRoute(
            self,
            "HeartbeatRoute",
            api_id=api.ref,
            route_key="heartbeat",
            target=f"integrations/{heartbeat_integration.ref}",
        )

        # Create refreshConnection custom route
        # Note: WebSocket custom routes don't support authorization at API Gateway level
        # Authorization must be implemented in the Lambda function itself
        refresh_route = apigwv2.CfnRoute(
            self,
            "RefreshRoute",
            api_id=api.ref,
            route_key="refreshConnection",
            target=f"integrations/{refresh_integration.ref}",
        )

        # Task 1.2: Create speaker control routes (pause, resume, mute, unmute, volume, state)
        # These routes map to the connection_handler Lambda which will be extended
        speaker_control_integration = self._create_lambda_integration(
            api, 
            self.connection_handler, 
            "SpeakerControlIntegration",
            timeout_ms=10000  # 10 seconds
        )
        
        pause_broadcast_route = apigwv2.CfnRoute(
            self,
            "PauseBroadcastRoute",
            api_id=api.ref,
            route_key="pauseBroadcast",
            target=f"integrations/{speaker_control_integration.ref}",
        )
        
        resume_broadcast_route = apigwv2.CfnRoute(
            self,
            "ResumeBroadcastRoute",
            api_id=api.ref,
            route_key="resumeBroadcast",
            target=f"integrations/{speaker_control_integration.ref}",
        )
        
        mute_broadcast_route = apigwv2.CfnRoute(
            self,
            "MuteBroadcastRoute",
            api_id=api.ref,
            route_key="muteBroadcast",
            target=f"integrations/{speaker_control_integration.ref}",
        )
        
        unmute_broadcast_route = apigwv2.CfnRoute(
            self,
            "UnmuteBroadcastRoute",
            api_id=api.ref,
            route_key="unmuteBroadcast",
            target=f"integrations/{speaker_control_integration.ref}",
        )
        
        set_volume_route = apigwv2.CfnRoute(
            self,
            "SetVolumeRoute",
            api_id=api.ref,
            route_key="setVolume",
            target=f"integrations/{speaker_control_integration.ref}",
        )
        
        speaker_state_change_route = apigwv2.CfnRoute(
            self,
            "SpeakerStateChangeRoute",
            api_id=api.ref,
            route_key="speakerStateChange",
            target=f"integrations/{speaker_control_integration.ref}",
        )

        # Task 1.3: Create session status route
        # Maps to session_status_handler Lambda
        session_status_integration = self._create_lambda_integration(
            api,
            self.session_status_handler,
            "SessionStatusIntegration",
            timeout_ms=5000  # 5 seconds
        )
        
        get_session_status_route = apigwv2.CfnRoute(
            self,
            "GetSessionStatusRoute",
            api_id=api.ref,
            route_key="getSessionStatus",
            target=f"integrations/{session_status_integration.ref}",
        )

        # Task 1.4: Create listener control routes (pausePlayback, changeLanguage)
        # These also map to connection_handler Lambda
        listener_control_integration = self._create_lambda_integration(
            api,
            self.connection_handler,
            "ListenerControlIntegration",
            timeout_ms=5000  # 5 seconds
        )
        
        pause_playback_route = apigwv2.CfnRoute(
            self,
            "PausePlaybackRoute",
            api_id=api.ref,
            route_key="pausePlayback",
            target=f"integrations/{listener_control_integration.ref}",
        )
        
        change_language_route = apigwv2.CfnRoute(
            self,
            "ChangeLanguageRoute",
            api_id=api.ref,
            route_key="changeLanguage",
            target=f"integrations/{listener_control_integration.ref}",
        )

        # Create audioChunk route (Phase 2) - speaker sends audio chunks
        audio_chunk_route = apigwv2.CfnRoute(
            self,
            "AudioChunkRoute",
            api_id=api.ref,
            route_key="audioChunk",
            target=f"integrations/{connect_integration.ref}",
        )

        # Create sendAudio route if audio_transcription_stack is provided
        send_audio_route = None
        if self.audio_transcription_stack:
            send_audio_route = apigwv2.CfnRoute(
                self,
                "SendAudioRoute",
                api_id=api.ref,
                route_key="sendAudio",
                target=f"integrations/{send_audio_integration.ref}",
            )

        # Create $default route to handle unmatched messages (CRITICAL for connection stability)
        default_route = apigwv2.CfnRoute(
            self,
            "DefaultRoute",
            api_id=api.ref,
            route_key="$default",
            target=f"integrations/{connect_integration.ref}",
        )

        # Create deployment
        deployment = apigwv2.CfnDeployment(
            self,
            "WebSocketDeployment",
            api_id=api.ref,
        )
        deployment.add_dependency(connect_route)
        deployment.add_dependency(disconnect_route)
        deployment.add_dependency(default_route)  # CRITICAL: Add $default route dependency
        deployment.add_dependency(create_session_route)
        deployment.add_dependency(join_session_route)
        deployment.add_dependency(heartbeat_route)
        deployment.add_dependency(refresh_route)
        # Add dependencies for new routes
        deployment.add_dependency(pause_broadcast_route)
        deployment.add_dependency(resume_broadcast_route)
        deployment.add_dependency(mute_broadcast_route)
        deployment.add_dependency(unmute_broadcast_route)
        deployment.add_dependency(set_volume_route)
        deployment.add_dependency(speaker_state_change_route)
        deployment.add_dependency(get_session_status_route)
        deployment.add_dependency(pause_playback_route)
        deployment.add_dependency(change_language_route)
        deployment.add_dependency(audio_chunk_route)  # Phase 2 addition
        # Add sendAudio route dependency if it exists
        if send_audio_route:
            deployment.add_dependency(send_audio_route)

        # Create stage with connection timeout settings
        # API Gateway WebSocket hard limits:
        # - Idle timeout: 10 minutes (600 seconds)
        # - Maximum connection duration: 2 hours (7200 seconds)
        stage = apigwv2.CfnStage(
            self,
            "WebSocketStage",
            api_id=api.ref,
            stage_name="prod",
            deployment_id=deployment.ref,
            default_route_settings=apigwv2.CfnStage.RouteSettingsProperty(
                throttling_burst_limit=5000,
                throttling_rate_limit=10000,
            ),
        )

        return api

    def _create_lambda_integration(
        self,
        api: apigwv2.CfnApi,
        function: lambda_.Function,
        integration_id: str,
        timeout_ms: int = 29000  # Default 29 seconds (API Gateway max is 29s)
    ) -> apigwv2.CfnIntegration:
        """
        Create Lambda integration for WebSocket API.
        
        Args:
            api: WebSocket API
            function: Lambda function
            integration_id: Integration construct ID
            timeout_ms: Integration timeout in milliseconds (default 29000ms)
            
        Returns:
            Integration
        """
        integration = apigwv2.CfnIntegration(
            self,
            integration_id,
            api_id=api.ref,
            integration_type="AWS_PROXY",
            integration_uri=f"arn:aws:apigateway:{self.region}:lambda:path/2015-03-31/functions/{function.function_arn}/invocations",
            timeout_in_millis=timeout_ms,
        )

        # Grant API Gateway permission to invoke Lambda
        function.add_permission(
            f"{integration_id}Permission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=f"arn:aws:execute-api:{self.region}:{self.account}:{api.ref}/*",
        )

        return integration

    def _create_periodic_status_update_rule(self):
        """
        Create EventBridge rule for periodic session status updates.
        
        This rule triggers the session_status_handler Lambda every 30 seconds
        to send automatic status updates to all active speakers.
        
        Requirements: 12 (Periodic Session Status Updates)
        """
        # Create EventBridge rule that triggers every 1 minute (minimum for EventBridge)
        # Note: EventBridge doesn't support sub-minute intervals
        rule = events.Rule(
            self,
            "PeriodicStatusUpdateRule",
            rule_name=f"session-status-periodic-update-{self.env_name}",
            description="Trigger periodic session status updates every 1 minute",
            schedule=events.Schedule.rate(Duration.minutes(1)),
            enabled=True,
        )

        # Add session_status_handler as target
        rule.add_target(
            targets.LambdaFunction(
                self.session_status_handler,
                retry_attempts=2,  # Retry up to 2 times on failure
            )
        )

        # Grant EventBridge permission to invoke the Lambda
        # This is automatically handled by add_target, but we can be explicit
        self.session_status_handler.grant_invoke(
            iam.ServicePrincipal("events.amazonaws.com")
        )

        # Add API Gateway endpoint to session_status_handler environment
        # This is needed for sending status updates to speakers via WebSocket
        api_endpoint = f"https://{self.websocket_api.ref}.execute-api.{self.region}.amazonaws.com/prod"
        self.session_status_handler.add_environment("API_GATEWAY_ENDPOINT", api_endpoint)

        # Grant API Gateway Management API permissions to session_status_handler
        # This allows it to send messages to WebSocket connections
        self.session_status_handler.add_to_role_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections", "execute-api:Invoke"],
                resources=[f"arn:aws:execute-api:{self.region}:{self.account}:{self.websocket_api.ref}/*"],
            )
        )

    def _create_alarm_topic(self) -> sns.Topic:
        """Create SNS topic for CloudWatch alarms."""
        topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name=f"session-management-alarms-{self.env_name}",
            display_name="Session Management CloudWatch Alarms"
        )
        
        # Add email subscription if configured
        alarm_email = self.config.get("alarmEmail")
        if alarm_email:
            sns.Subscription(
                self,
                "AlarmEmailSubscription",
                topic=topic,
                protocol=sns.SubscriptionProtocol.EMAIL,
                endpoint=alarm_email
            )
        
        return topic

    def _create_kvs_stream_consumer(self) -> lambda_.Function:
        """Create KVS Stream Consumer Lambda function (Phase 3)."""
        # Get log retention from config
        log_retention_hours = int(self.config.get("dataRetentionHours", 12))
        log_retention = logs.RetentionDays.ONE_DAY
        
        # Get audio processor function name for invoking from KVS consumer
        audio_processor_function_name = "audio-processor-dev"
        if self.audio_transcription_stack:
            audio_processor_function_name = self.audio_transcription_stack.audio_processor_function.function_name
        
        function = lambda_.Function(
            self,
            "KVSStreamConsumer",
            function_name=f"kvs-stream-consumer-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/kvs_stream_consumer"),
            layers=[self.shared_layer],
            timeout=Duration.minutes(15),  # Long timeout for stream processing
            memory_size=1024,  # Higher memory for audio processing
            environment={
                "ENV": self.env_name,
                "SESSIONS_TABLE": self.sessions_table.table_name,
                "CONNECTIONS_TABLE": self.connections_table.table_name,
                "AUDIO_PROCESSOR_FUNCTION_NAME": audio_processor_function_name,
                "REGION": self.config.get("region", "us-east-1"),
            },
            log_retention=log_retention,
        )

        # Grant DynamoDB permissions
        self.sessions_table.grant_read_data(function)
        self.connections_table.grant_read_data(function)

        # Grant KVS permissions for stream consumption
        function.add_to_role_policy(
            iam.PolicyStatement(
                sid="KVSStreamConsumption",
                actions=[
                    "kinesisvideo:GetDataEndpoint",
                    "kinesisvideo:GetMedia",
                    "kinesisvideo:DescribeStream",
                    "kinesisvideo:ListStreams",
                ],
                resources=[
                    f"arn:aws:kinesisvideo:{self.region}:{self.account}:stream/session-*/*"
                ],
            )
        )

        # Grant KVS-video-media permissions for GetMedia API
        function.add_to_role_policy(
            iam.PolicyStatement(
                sid="KVSMediaAccess",
                actions=[
                    "kinesis-video-media:GetMedia",
                ],
                resources=["*"],  # KVS media endpoints are dynamic
            )
        )

        # Grant Lambda invoke permissions for audio processor
        function.add_to_role_policy(
            iam.PolicyStatement(
                sid="InvokeAudioProcessor",
                actions=[
                    "lambda:InvokeFunction",
                ],
                resources=[
                    f"arn:aws:lambda:{self.region}:{self.account}:function:{audio_processor_function_name}*"
                ],
            )
        )

        # Grant CloudWatch permissions for metrics
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=['cloudwatch:PutMetricData'],
                resources=['*']
            )
        )

        return function

    def _create_kvs_event_rules(self):
        """
        Create EventBridge rules for KVS stream processing (Phase 3).
        
        Creates rules to:
        1. Trigger KVS consumer when sessions become active
        2. Stop KVS consumer when sessions end
        3. Health check and cleanup for KVS consumer
        """
        # Rule 1: Session lifecycle events
        # This rule will be triggered by session creation/deletion events
        # For now, we'll create a placeholder rule - in production this would
        # be triggered by the HTTP session handler when sessions are created
        
        session_lifecycle_rule = events.Rule(
            self,
            "SessionLifecycleRule",
            rule_name=f"session-lifecycle-{self.env_name}",
            description="Trigger KVS stream processing on session lifecycle events",
            event_pattern=events.EventPattern(
                source=["session-management"],
                detail_type=["Session Status Change"],
                detail={
                    "status": ["ACTIVE", "ENDED"]
                }
            ),
            enabled=True,
        )

        # Add KVS stream consumer as target for session lifecycle events
        session_lifecycle_rule.add_target(
            targets.LambdaFunction(
                self.kvs_stream_consumer,
                retry_attempts=2,
            )
        )

        # Grant EventBridge permission to invoke KVS stream consumer
        self.kvs_stream_consumer.grant_invoke(
            iam.ServicePrincipal("events.amazonaws.com")
        )

        # Rule 2: Periodic health check and cleanup for KVS consumer
        kvs_health_check_rule = events.Rule(
            self,
            "KVSHealthCheckRule",
            rule_name=f"kvs-health-check-{self.env_name}",
            description="Periodic health check and cleanup for KVS stream consumer",
            schedule=events.Schedule.rate(Duration.minutes(5)),  # Every 5 minutes
            enabled=True,
        )

        # Add KVS stream consumer as target with health check payload
        kvs_health_check_rule.add_target(
            targets.LambdaFunction(
                self.kvs_stream_consumer,
                retry_attempts=1,
                event=events.RuleTargetInput.from_object({
                    "action": "health_check",
                    "source": "cloudwatch_events"
                })
            )
        )

    def _create_cloudwatch_alarms(self):
        """Create CloudWatch alarms for monitoring."""
        # Alarm action
        alarm_action = cw_actions.SnsAction(self.alarm_topic)
        
        # 1. Session Creation Latency Alarm (p95 > 2000ms)
        session_creation_latency_alarm = cloudwatch.Alarm(
            self,
            "SessionCreationLatencyAlarm",
            alarm_name=f"session-creation-latency-{self.env_name}",
            alarm_description="Alert when session creation p95 latency exceeds 2000ms",
            metric=cloudwatch.Metric(
                namespace="SessionManagement",
                metric_name="SessionCreationLatency",
                statistic="p95",
                period=Duration.minutes(5)
            ),
            threshold=2000,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        session_creation_latency_alarm.add_alarm_action(alarm_action)
        
        # 2. Connection Errors Alarm (> 100 per 5 minutes)
        connection_errors_alarm = cloudwatch.Alarm(
            self,
            "ConnectionErrorsAlarm",
            alarm_name=f"connection-errors-{self.env_name}",
            alarm_description="Alert when connection errors exceed 100 per 5 minutes",
            metric=cloudwatch.Metric(
                namespace="SessionManagement",
                metric_name="ConnectionErrors",
                statistic="Sum",
                period=Duration.minutes(5)
            ),
            threshold=100,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        connection_errors_alarm.add_alarm_action(alarm_action)
        
        # 3. Active Sessions Approaching Limit Alarm
        # Assuming a limit of 100 active sessions, alert at 90
        max_sessions = int(self.config.get("maxActiveSessions", 100))
        active_sessions_alarm = cloudwatch.Alarm(
            self,
            "ActiveSessionsAlarm",
            alarm_name=f"active-sessions-limit-{self.env_name}",
            alarm_description=f"Alert when active sessions approach limit ({max_sessions})",
            metric=cloudwatch.Metric(
                namespace="SessionManagement",
                metric_name="ActiveSessions",
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=max_sessions * 0.9,  # Alert at 90% of limit
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        active_sessions_alarm.add_alarm_action(alarm_action)
        
        # 4. Lambda Error Rate Alarms for each function
        for function_name, function in [
            ("connection-handler", self.connection_handler),
            ("heartbeat-handler", self.heartbeat_handler),
            ("disconnect-handler", self.disconnect_handler),
            ("refresh-handler", self.refresh_handler),
            ("kvs-stream-consumer", self.kvs_stream_consumer),  # Phase 3 addition
        ]:
            error_alarm = cloudwatch.Alarm(
                self,
                f"{function_name.title().replace('-', '')}ErrorAlarm",
                alarm_name=f"{function_name}-errors-{self.env_name}",
                alarm_description=f"Alert when {function_name} error rate is high",
                metric=function.metric_errors(
                    statistic="Sum",
                    period=Duration.minutes(5)
                ),
                threshold=10,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
            )
            error_alarm.add_alarm_action(alarm_action)
        
        # 5. KVS Stream Consumer specific alarms (Phase 3)
        # Active streams count alarm
        kvs_active_streams_alarm = cloudwatch.Alarm(
            self,
            "KVSActiveStreamsAlarm",
            alarm_name=f"kvs-active-streams-{self.env_name}",
            alarm_description="Alert when KVS active streams exceed expected threshold",
            metric=cloudwatch.Metric(
                namespace="KVSStreamConsumer",
                metric_name="ActiveStreams",
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=20,  # Alert if more than 20 concurrent streams
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        kvs_active_streams_alarm.add_alarm_action(alarm_action)

    def _create_outputs(self):
        """Create CloudFormation outputs."""
        CfnOutput(
            self,
            "SessionsTableName",
            value=self.sessions_table.table_name,
            description="Sessions DynamoDB table name"
        )

        CfnOutput(
            self,
            "ConnectionsTableName",
            value=self.connections_table.table_name,
            description="Connections DynamoDB table name"
        )

        CfnOutput(
            self,
            "RateLimitsTableName",
            value=self.rate_limits_table.table_name,
            description="RateLimits DynamoDB table name"
        )

        CfnOutput(
            self,
            "WebSocketAPIEndpoint",
            value=f"wss://{self.websocket_api.ref}.execute-api.{self.region}.amazonaws.com/prod",
            description="WebSocket API endpoint URL"
        )
        
        CfnOutput(
            self,
            "AlarmTopicArn",
            value=self.alarm_topic.topic_arn,
            description="SNS topic ARN for CloudWatch alarms"
        )
        
        # Phase 2 outputs
        CfnOutput(
            self,
            "KVSStreamWriterFunctionName",
            value=self.kvs_stream_writer.function_name,
            description="KVS Stream Writer Lambda function name"
        )
        
        CfnOutput(
            self,
            "KVSStreamWriterFunctionArn",
            value=self.kvs_stream_writer.function_arn,
            description="KVS Stream Writer Lambda function ARN"
        )
        
        # Phase 3 outputs
        CfnOutput(
            self,
            "S3AudioConsumerFunctionName",
            value=self.s3_audio_consumer.function_name,
            description="S3 Audio Consumer Lambda function name"
        )
        
        CfnOutput(
            self,
            "S3AudioConsumerFunctionArn",
            value=self.s3_audio_consumer.function_arn,
            description="S3 Audio Consumer Lambda function ARN"
        )
        
        CfnOutput(
            self,
            "KVSStreamConsumerFunctionName",
            value=self.kvs_stream_consumer.function_name,
            description="KVS Stream Consumer Lambda function name"
        )
        
        CfnOutput(
            self,
            "KVSStreamConsumerFunctionArn",
            value=self.kvs_stream_consumer.function_arn,
            description="KVS Stream Consumer Lambda function ARN"
        )
