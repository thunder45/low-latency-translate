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

        # Create WebSocket API (placeholder - will be implemented in later tasks)
        # self.websocket_api = self._create_websocket_api()

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
