"""
CDK Stack for Session Management Infrastructure.
"""
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigatewayv2 as apigwv2,
    aws_logs as logs,
    aws_iam as iam,
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
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.config = config
        self.env_name = env_name

        # Create DynamoDB tables
        self.sessions_table = self._create_sessions_table()
        self.connections_table = self._create_connections_table()
        self.rate_limits_table = self._create_rate_limits_table()

        # Create Lambda functions
        self.authorizer_function = self._create_authorizer_function()
        self.connection_handler = self._create_connection_handler()
        self.heartbeat_handler = self._create_heartbeat_handler()
        self.disconnect_handler = self._create_disconnect_handler()
        self.refresh_handler = self._create_refresh_handler()

        # Create WebSocket API
        self.websocket_api = self._create_websocket_api()

        # Outputs
        self._create_outputs()

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

    def _create_authorizer_function(self) -> lambda_.Function:
        """Create Lambda Authorizer function."""
        function = lambda_.Function(
            self,
            "AuthorizerFunction",
            function_name=f"session-authorizer-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/authorizer"),
            timeout=Duration.seconds(10),
            environment={
                "ENV": self.env_name,
                "REGION": self.config.get("region", "us-east-1"),
                "USER_POOL_ID": self.config.get("cognitoUserPoolId", ""),
                "CLIENT_ID": self.config.get("cognitoClientId", ""),
            },
            log_retention=logs.RetentionDays.ONE_DAY if self.env_name == "dev" else logs.RetentionDays.ONE_WEEK,
        )
        return function

    def _create_connection_handler(self) -> lambda_.Function:
        """Create Connection Handler function."""
        function = lambda_.Function(
            self,
            "ConnectionHandler",
            function_name=f"session-connection-handler-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/connection_handler"),
            timeout=Duration.seconds(30),
            environment={
                "ENV": self.env_name,
                "SESSIONS_TABLE": self.sessions_table.table_name,
                "CONNECTIONS_TABLE": self.connections_table.table_name,
                "RATE_LIMITS_TABLE": self.rate_limits_table.table_name,
                "SESSION_MAX_DURATION_HOURS": str(self.config.get("sessionMaxDurationHours", 2)),
                "MAX_LISTENERS_PER_SESSION": str(self.config.get("maxListenersPerSession", 500)),
            },
            log_retention=logs.RetentionDays.ONE_DAY if self.env_name == "dev" else logs.RetentionDays.ONE_WEEK,
        )

        # Grant DynamoDB permissions
        self.sessions_table.grant_read_write_data(function)
        self.connections_table.grant_read_write_data(function)
        self.rate_limits_table.grant_read_write_data(function)

        return function

    def _create_heartbeat_handler(self) -> lambda_.Function:
        """Create Heartbeat Handler function."""
        function = lambda_.Function(
            self,
            "HeartbeatHandler",
            function_name=f"session-heartbeat-handler-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/heartbeat_handler"),
            timeout=Duration.seconds(10),
            environment={
                "ENV": self.env_name,
                "CONNECTIONS_TABLE": self.connections_table.table_name,
                "CONNECTION_REFRESH_MINUTES": str(self.config.get("connectionRefreshMinutes", 100)),
                "CONNECTION_WARNING_MINUTES": str(self.config.get("connectionWarningMinutes", 105)),
            },
            log_retention=logs.RetentionDays.ONE_DAY if self.env_name == "dev" else logs.RetentionDays.ONE_WEEK,
        )

        # Grant DynamoDB permissions
        self.connections_table.grant_read_data(function)

        return function

    def _create_disconnect_handler(self) -> lambda_.Function:
        """Create Disconnect Handler function."""
        function = lambda_.Function(
            self,
            "DisconnectHandler",
            function_name=f"session-disconnect-handler-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/disconnect_handler"),
            timeout=Duration.seconds(30),
            environment={
                "ENV": self.env_name,
                "SESSIONS_TABLE": self.sessions_table.table_name,
                "CONNECTIONS_TABLE": self.connections_table.table_name,
            },
            log_retention=logs.RetentionDays.ONE_DAY if self.env_name == "dev" else logs.RetentionDays.ONE_WEEK,
        )

        # Grant DynamoDB permissions
        self.sessions_table.grant_read_write_data(function)
        self.connections_table.grant_read_write_data(function)

        return function

    def _create_refresh_handler(self) -> lambda_.Function:
        """Create Connection Refresh Handler function."""
        function = lambda_.Function(
            self,
            "RefreshHandler",
            function_name=f"session-refresh-handler-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../lambda/refresh_handler"),
            timeout=Duration.seconds(30),
            environment={
                "ENV": self.env_name,
                "SESSIONS_TABLE": self.sessions_table.table_name,
                "CONNECTIONS_TABLE": self.connections_table.table_name,
            },
            log_retention=logs.RetentionDays.ONE_DAY if self.env_name == "dev" else logs.RetentionDays.ONE_WEEK,
        )

        # Grant DynamoDB permissions
        self.sessions_table.grant_read_write_data(function)
        self.connections_table.grant_read_write_data(function)

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
        authorizer = apigwv2.CfnAuthorizer(
            self,
            "WebSocketAuthorizer",
            api_id=api.ref,
            name=f"session-authorizer-{self.env_name}",
            authorizer_type="REQUEST",
            authorizer_uri=f"arn:aws:apigateway:{self.region}:lambda:path/2015-03-31/functions/{self.authorizer_function.function_arn}/invocations",
            identity_source=["route.request.querystring.token"],
        )

        # Grant API Gateway permission to invoke authorizer
        self.authorizer_function.add_permission(
            "AuthorizerInvokePermission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=f"arn:aws:execute-api:{self.region}:{self.account}:{api.ref}/*",
        )

        # Create Lambda integrations
        connect_integration = self._create_lambda_integration(api, self.connection_handler, "ConnectIntegration")
        disconnect_integration = self._create_lambda_integration(api, self.disconnect_handler, "DisconnectIntegration")
        heartbeat_integration = self._create_lambda_integration(api, self.heartbeat_handler, "HeartbeatIntegration")
        refresh_integration = self._create_lambda_integration(api, self.refresh_handler, "RefreshIntegration")

        # Update Lambda environment with API Gateway endpoint (will be set after deployment)
        # This is a placeholder - actual endpoint will be available after deployment
        api_endpoint = f"https://{api.ref}.execute-api.{self.region}.amazonaws.com/prod"
        
        # Update heartbeat handler with API endpoint
        self.heartbeat_handler.add_environment("API_GATEWAY_ENDPOINT", api_endpoint)
        self.refresh_handler.add_environment("API_GATEWAY_ENDPOINT", api_endpoint)
        self.disconnect_handler.add_environment("API_GATEWAY_ENDPOINT", api_endpoint)

        # Grant API Gateway Management API permissions
        for function in [self.heartbeat_handler, self.refresh_handler, self.disconnect_handler]:
            function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["execute-api:ManageConnections"],
                    resources=[f"arn:aws:execute-api:{self.region}:{self.account}:{api.ref}/*"],
                )
            )

        # Create $connect route (with authorizer for speakers)
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

        # Create heartbeat custom route
        heartbeat_route = apigwv2.CfnRoute(
            self,
            "HeartbeatRoute",
            api_id=api.ref,
            route_key="heartbeat",
            target=f"integrations/{heartbeat_integration.ref}",
        )

        # Create refreshConnection custom route (with authorizer for speakers)
        refresh_route = apigwv2.CfnRoute(
            self,
            "RefreshRoute",
            api_id=api.ref,
            route_key="refreshConnection",
            authorization_type="CUSTOM",
            authorizer_id=authorizer.ref,
            target=f"integrations/{refresh_integration.ref}",
        )

        # Create deployment
        deployment = apigwv2.CfnDeployment(
            self,
            "WebSocketDeployment",
            api_id=api.ref,
        )
        deployment.add_dependency(connect_route)
        deployment.add_dependency(disconnect_route)
        deployment.add_dependency(heartbeat_route)
        deployment.add_dependency(refresh_route)

        # Create stage
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
        integration_id: str
    ) -> apigwv2.CfnIntegration:
        """
        Create Lambda integration for WebSocket API.
        
        Args:
            api: WebSocket API
            function: Lambda function
            integration_id: Integration construct ID
            
        Returns:
            Integration
        """
        integration = apigwv2.CfnIntegration(
            self,
            integration_id,
            api_id=api.ref,
            integration_type="AWS_PROXY",
            integration_uri=f"arn:aws:apigateway:{self.region}:lambda:path/2015-03-31/functions/{function.function_arn}/invocations",
        )

        # Grant API Gateway permission to invoke Lambda
        function.add_permission(
            f"{integration_id}Permission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=f"arn:aws:execute-api:{self.region}:{self.account}:{api.ref}/*",
        )

        return integration

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
