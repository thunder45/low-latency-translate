"""
CDK Stack for Translation Broadcasting Pipeline Infrastructure.

This stack defines the infrastructure for the translation and broadcasting pipeline including:
- DynamoDB tables for sessions, connections, and translation cache
- Lambda functions for translation and broadcasting
- IAM roles and permissions
- CloudWatch alarms and monitoring
"""
import os

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
)
from constructs import Construct


class TranslationPipelineStack(Stack):
    """
    CDK Stack for Translation Broadcasting Pipeline.
    
    Includes:
    - Sessions table with listenerCount atomic counter
    - Connections table with sessionId-targetLanguage GSI
    - CachedTranslations table with TTL enabled
    - Lambda functions for translation and broadcasting
    - CloudWatch alarms for monitoring
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
        self.cached_translations_table = self._create_cached_translations_table()

        # Create SNS topic for alarms
        self.alarm_topic = self._create_alarm_topic()

        # Create Lambda layer for shared code
        self.shared_layer = self._create_shared_layer()

        # Create Lambda function
        self.translation_processor_function = self._create_translation_processor_function()

        # Create CloudWatch alarms
        self._create_cloudwatch_alarms()

        # Create CloudWatch dashboard
        self.dashboard = self._create_cloudwatch_dashboard()

        # Outputs
        self._create_outputs()

    def _create_sessions_table(self) -> dynamodb.Table:
        """
        Create Sessions DynamoDB table with listenerCount atomic counter.
        
        Table structure:
        - Partition Key: sessionId (string)
        - Attributes: speakerConnectionId, sourceLanguage, listenerCount (number),
                     isActive, createdAt, expiresAt (TTL)
        
        Requirements: 2.1, 9.1
        """
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
            point_in_time_recovery=True if self.env_name == "prod" else False,
        )
        
        return table

    def _create_connections_table(self) -> dynamodb.Table:
        """
        Create Connections DynamoDB table with sessionId-targetLanguage GSI.
        
        Table structure:
        - Partition Key: connectionId (string)
        - Attributes: sessionId, targetLanguage, role, connectedAt, ttl
        - GSI: sessionId-targetLanguage-index
          - Partition Key: sessionId
          - Sort Key: targetLanguage
          - Projection: ALL
        
        This GSI enables efficient queries for:
        1. Get unique target languages for a session
        2. Get all listeners for a specific language
        
        Requirements: 2.2, 2.3, 2.4, 2.5
        """
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
            point_in_time_recovery=True if self.env_name == "prod" else False,
        )

        # Add Global Secondary Index for efficient language-based queries
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

    def _create_cached_translations_table(self) -> dynamodb.Table:
        """
        Create CachedTranslations DynamoDB table with TTL enabled.
        
        Table structure:
        - Partition Key: cacheKey (string) - format: {source}:{target}:{hash16}
        - Attributes: sourceLanguage, targetLanguage, sourceText, translatedText,
                     createdAt, accessCount, lastAccessedAt, ttl
        - TTL: 3600 seconds (1 hour)
        - Max entries: 10,000 with LRU eviction
        
        Cache key format:
        - {sourceLanguage}:{targetLanguage}:{textHash}
        - Example: "en:es:3f7b2a1c9d8e5f4a"
        - textHash: First 16 chars of SHA-256 hash of normalized text
        
        Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8
        """
        table = dynamodb.Table(
            self,
            "CachedTranslationsTable",
            table_name=f"CachedTranslations-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="cacheKey",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True if self.env_name == "prod" else False,
        )

        return table

    def _create_shared_layer(self) -> lambda_.LayerVersion:
        """
        Create Lambda layer with shared code.
        
        The layer includes all shared modules from the shared/ directory.
        """
        # Determine the correct path to shared code
        # When running from infrastructure directory, use ../shared
        # When running tests, the path is relative to the test location
        shared_path = os.path.join(os.path.dirname(__file__), "..", "..", "shared")
        
        layer = lambda_.LayerVersion(
            self,
            "SharedLayer",
            layer_version_name=f"translation-pipeline-shared-{self.env_name}",
            code=lambda_.Code.from_asset(shared_path),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="Shared code for translation pipeline Lambda functions"
        )
        
        return layer

    def _create_translation_processor_function(self) -> lambda_.Function:
        """
        Create Lambda function for translation processing.
        
        Configuration:
        - Runtime: Python 3.11
        - Memory: 1024 MB
        - Timeout: 30 seconds
        - Environment variables for DynamoDB tables and configuration
        - IAM permissions for DynamoDB, Translate, Polly, API Gateway
        
        Requirements: 10.1, 10.2, 10.3
        """
        # Create IAM role for Lambda
        lambda_role = iam.Role(
            self,
            "TranslationProcessorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for translation processor Lambda function"
        )
        
        # Add basic Lambda execution permissions
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )
        
        # Grant DynamoDB permissions
        self.sessions_table.grant_read_write_data(lambda_role)
        self.connections_table.grant_read_write_data(lambda_role)
        self.cached_translations_table.grant_read_write_data(lambda_role)
        
        # Grant permissions for GSI queries
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:Query"
                ],
                resources=[
                    f"{self.connections_table.table_arn}/index/*"
                ]
            )
        )
        
        # Grant AWS Translate permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "translate:TranslateText"
                ],
                resources=["*"]
            )
        )
        
        # Grant AWS Polly permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "polly:SynthesizeSpeech"
                ],
                resources=["*"]
            )
        )
        
        # Grant API Gateway Management API permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "execute-api:ManageConnections"
                ],
                resources=[
                    f"arn:aws:execute-api:{self.region}:{self.account}:*/@connections/*"
                ]
            )
        )
        
        # Grant CloudWatch metrics permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:PutMetricData"
                ],
                resources=["*"]
            )
        )
        
        # Get API Gateway endpoint from config
        api_gateway_endpoint = self.config.get(
            "apiGatewayEndpoint",
            f"https://{{api-id}}.execute-api.{self.region}.amazonaws.com/{self.env_name}"
        )
        
        # Determine the correct path to Lambda function code
        lambda_path = os.path.join(os.path.dirname(__file__), "..", "..", "lambda", "translation_processor")
        
        # Create Lambda function
        function = lambda_.Function(
            self,
            "TranslationProcessorFunction",
            function_name=f"translation-processor-{self.env_name}",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(lambda_path),
            role=lambda_role,
            memory_size=1024,
            timeout=Duration.seconds(30),
            layers=[self.shared_layer],
            environment={
                "SESSIONS_TABLE_NAME": self.sessions_table.table_name,
                "CONNECTIONS_TABLE_NAME": self.connections_table.table_name,
                "CACHED_TRANSLATIONS_TABLE_NAME": self.cached_translations_table.table_name,
                "MAX_CONCURRENT_BROADCASTS": str(
                    self.config.get("maxConcurrentBroadcasts", 100)
                ),
                "CACHE_TTL_SECONDS": str(
                    self.config.get("cacheTtlSeconds", 3600)
                ),
                "MAX_CACHE_ENTRIES": str(
                    self.config.get("maxCacheEntries", 10000)
                ),
                "API_GATEWAY_ENDPOINT": api_gateway_endpoint
            },
            log_retention=logs.RetentionDays.ONE_WEEK if self.env_name == "dev" else logs.RetentionDays.ONE_MONTH,
            tracing=lambda_.Tracing.ACTIVE if self.env_name == "prod" else lambda_.Tracing.DISABLED
        )
        
        return function

    def _create_alarm_topic(self) -> sns.Topic:
        """Create SNS topic for CloudWatch alarms."""
        topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name=f"translation-pipeline-alarms-{self.env_name}",
            display_name="Translation Pipeline CloudWatch Alarms"
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

    def _create_cloudwatch_alarms(self):
        """
        Create CloudWatch alarms for monitoring translation pipeline.
        
        Alarms:
        1. Cache hit rate < 30%
        2. Broadcast success rate < 95%
        3. Buffer overflow rate > 5%
        4. Failed languages > 10%
        """
        # Alarm action
        alarm_action = cw_actions.SnsAction(self.alarm_topic)
        
        # 1. Cache Hit Rate Alarm (< 30%)
        cache_hit_rate_alarm = cloudwatch.Alarm(
            self,
            "CacheHitRateAlarm",
            alarm_name=f"translation-cache-hit-rate-low-{self.env_name}",
            alarm_description="Alert when translation cache hit rate falls below 30%",
            metric=cloudwatch.Metric(
                namespace="TranslationPipeline",
                metric_name="CacheHitRate",
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=30,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        cache_hit_rate_alarm.add_alarm_action(alarm_action)
        
        # 2. Broadcast Success Rate Alarm (< 95%)
        broadcast_success_alarm = cloudwatch.Alarm(
            self,
            "BroadcastSuccessRateAlarm",
            alarm_name=f"broadcast-success-rate-low-{self.env_name}",
            alarm_description="Alert when broadcast success rate falls below 95%",
            metric=cloudwatch.Metric(
                namespace="TranslationPipeline",
                metric_name="BroadcastSuccessRate",
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=95,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        broadcast_success_alarm.add_alarm_action(alarm_action)
        
        # 3. Buffer Overflow Rate Alarm (> 5%)
        buffer_overflow_alarm = cloudwatch.Alarm(
            self,
            "BufferOverflowRateAlarm",
            alarm_name=f"buffer-overflow-rate-high-{self.env_name}",
            alarm_description="Alert when buffer overflow rate exceeds 5%",
            metric=cloudwatch.Metric(
                namespace="TranslationPipeline",
                metric_name="BufferOverflowRate",
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=5,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        buffer_overflow_alarm.add_alarm_action(alarm_action)
        
        # 4. Failed Languages Alarm (> 10%)
        failed_languages_alarm = cloudwatch.Alarm(
            self,
            "FailedLanguagesAlarm",
            alarm_name=f"failed-languages-high-{self.env_name}",
            alarm_description="Alert when failed languages exceed 10%",
            metric=cloudwatch.Metric(
                namespace="TranslationPipeline",
                metric_name="FailedLanguagesCount",
                statistic="Sum",
                period=Duration.minutes(5)
            ),
            threshold=10,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        failed_languages_alarm.add_alarm_action(alarm_action)

    def _create_cloudwatch_dashboard(self) -> cloudwatch.Dashboard:
        """
        Create CloudWatch dashboard for translation pipeline metrics.
        
        Dashboard includes:
        - Cache performance metrics (hit rate, size, evictions)
        - Translation metrics (languages processed, failed)
        - Synthesis metrics (duration, success rate)
        - Broadcast metrics (success rate, latency)
        - Buffer metrics (overflow rate, utilization)
        - Lambda metrics (invocations, errors, duration)
        """
        dashboard = cloudwatch.Dashboard(
            self,
            "TranslationPipelineDashboard",
            dashboard_name=f"TranslationPipeline-{self.env_name}"
        )
        
        # Row 1: Cache Performance
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Cache Hit Rate",
                left=[
                    cloudwatch.Metric(
                        namespace="TranslationPipeline",
                        metric_name="CacheHitRate",
                        statistic="Average",
                        period=Duration.minutes(5),
                        label="Hit Rate (%)"
                    )
                ],
                width=8,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Cache Size",
                left=[
                    cloudwatch.Metric(
                        namespace="TranslationPipeline",
                        metric_name="CacheSize",
                        statistic="Average",
                        period=Duration.minutes(5),
                        label="Entries"
                    )
                ],
                width=8,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Cache Evictions",
                left=[
                    cloudwatch.Metric(
                        namespace="TranslationPipeline",
                        metric_name="CacheEvictions",
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Evictions"
                    )
                ],
                width=8,
                height=6
            )
        )
        
        # Row 2: Translation & Synthesis
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Languages Processed",
                left=[
                    cloudwatch.Metric(
                        namespace="TranslationPipeline",
                        metric_name="LanguagesProcessed",
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Processed"
                    ),
                    cloudwatch.Metric(
                        namespace="TranslationPipeline",
                        metric_name="FailedLanguagesCount",
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Failed"
                    )
                ],
                width=12,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Processing Duration",
                left=[
                    cloudwatch.Metric(
                        namespace="TranslationPipeline",
                        metric_name="ProcessingDuration",
                        statistic="Average",
                        period=Duration.minutes(5),
                        label="Avg (ms)"
                    ),
                    cloudwatch.Metric(
                        namespace="TranslationPipeline",
                        metric_name="ProcessingDuration",
                        statistic="p99",
                        period=Duration.minutes(5),
                        label="P99 (ms)"
                    )
                ],
                width=12,
                height=6
            )
        )
        
        # Row 3: Broadcast Performance
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Broadcast Success Rate",
                left=[
                    cloudwatch.Metric(
                        namespace="TranslationPipeline",
                        metric_name="BroadcastSuccessRate",
                        statistic="Average",
                        period=Duration.minutes(5),
                        label="Success Rate (%)"
                    )
                ],
                width=12,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Buffer Overflow Rate",
                left=[
                    cloudwatch.Metric(
                        namespace="TranslationPipeline",
                        metric_name="BufferOverflowRate",
                        statistic="Average",
                        period=Duration.minutes(5),
                        label="Overflow Rate (%)"
                    )
                ],
                width=12,
                height=6
            )
        )
        
        # Row 4: Listener Metrics
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Active Listeners",
                left=[
                    cloudwatch.Metric(
                        namespace="TranslationPipeline",
                        metric_name="ListenerCount",
                        statistic="Average",
                        period=Duration.minutes(5),
                        label="Listeners"
                    )
                ],
                width=24,
                height=6
            )
        )
        
        # Row 5: Lambda Performance
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Lambda Invocations",
                left=[
                    self.translation_processor_function.metric_invocations(
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Invocations"
                    ),
                    self.translation_processor_function.metric_errors(
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Errors"
                    )
                ],
                width=8,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Lambda Duration",
                left=[
                    self.translation_processor_function.metric_duration(
                        statistic="Average",
                        period=Duration.minutes(5),
                        label="Avg (ms)"
                    ),
                    self.translation_processor_function.metric_duration(
                        statistic="p99",
                        period=Duration.minutes(5),
                        label="P99 (ms)"
                    )
                ],
                width=8,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Lambda Throttles",
                left=[
                    self.translation_processor_function.metric_throttles(
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Throttles"
                    )
                ],
                width=8,
                height=6
            )
        )
        
        # Row 6: DynamoDB Performance
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="DynamoDB Read Capacity",
                left=[
                    self.sessions_table.metric_consumed_read_capacity_units(
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Sessions"
                    ),
                    self.connections_table.metric_consumed_read_capacity_units(
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Connections"
                    ),
                    self.cached_translations_table.metric_consumed_read_capacity_units(
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Cache"
                    )
                ],
                width=12,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="DynamoDB Write Capacity",
                left=[
                    self.sessions_table.metric_consumed_write_capacity_units(
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Sessions"
                    ),
                    self.connections_table.metric_consumed_write_capacity_units(
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Connections"
                    ),
                    self.cached_translations_table.metric_consumed_write_capacity_units(
                        statistic="Sum",
                        period=Duration.minutes(5),
                        label="Cache"
                    )
                ],
                width=12,
                height=6
            )
        )
        
        return dashboard

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
            "SessionsTableArn",
            value=self.sessions_table.table_arn,
            description="Sessions DynamoDB table ARN"
        )

        CfnOutput(
            self,
            "ConnectionsTableName",
            value=self.connections_table.table_name,
            description="Connections DynamoDB table name"
        )

        CfnOutput(
            self,
            "ConnectionsTableArn",
            value=self.connections_table.table_arn,
            description="Connections DynamoDB table ARN"
        )

        CfnOutput(
            self,
            "ConnectionsGSIName",
            value="sessionId-targetLanguage-index",
            description="Connections table GSI name for language-based queries"
        )

        CfnOutput(
            self,
            "CachedTranslationsTableName",
            value=self.cached_translations_table.table_name,
            description="CachedTranslations DynamoDB table name"
        )

        CfnOutput(
            self,
            "CachedTranslationsTableArn",
            value=self.cached_translations_table.table_arn,
            description="CachedTranslations DynamoDB table ARN"
        )
        
        CfnOutput(
            self,
            "AlarmTopicArn",
            value=self.alarm_topic.topic_arn,
            description="SNS topic ARN for CloudWatch alarms"
        )
        
        CfnOutput(
            self,
            "TranslationProcessorFunctionName",
            value=self.translation_processor_function.function_name,
            description="Translation processor Lambda function name"
        )
        
        CfnOutput(
            self,
            "TranslationProcessorFunctionArn",
            value=self.translation_processor_function.function_arn,
            description="Translation processor Lambda function ARN"
        )
        
        CfnOutput(
            self,
            "SharedLayerArn",
            value=self.shared_layer.layer_version_arn,
            description="Shared code Lambda layer ARN"
        )
        
        CfnOutput(
            self,
            "DashboardName",
            value=self.dashboard.dashboard_name,
            description="CloudWatch dashboard name"
        )
