"""
CDK Stack for HTTP API Gateway and Session Management.

This stack implements the HTTP REST API for session CRUD operations,
separating stateless session management from stateful WebSocket communication.
"""
from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_apigatewayv2 as apigwv2,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_logs as logs,
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class HttpApiStack(Stack):
    """
    CDK stack for HTTP API Gateway and session management.
    
    Provides REST API endpoints for session CRUD operations:
    - POST /sessions - Create new session
    - GET /sessions/{sessionId} - Retrieve session details
    - PATCH /sessions/{sessionId} - Update session
    - DELETE /sessions/{sessionId} - Delete session
    - GET /health - Health check endpoint
    """
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        sessions_table: dynamodb.Table,
        connections_table: dynamodb.Table,
        user_pool: cognito.UserPool,
        shared_layer: lambda_.LayerVersion,
        env_name: str,
        config: dict,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.sessions_table = sessions_table
        self.connections_table = connections_table
        self.user_pool = user_pool
        self.shared_layer = shared_layer
        self.env_name = env_name
        self.config = config
        
        # Create Lambda function for session handler
        self.session_handler = self._create_session_handler()
        
        # Create HTTP API
        self.http_api = self._create_http_api()
        
        # Create JWT authorizer
        self.jwt_authorizer = self._create_jwt_authorizer()
        
        # Add routes
        self._add_routes()
        
        # Create outputs
        self._create_outputs()
    
    def _create_session_handler(self) -> lambda_.Function:
        """Create Lambda function for HTTP session CRUD operations."""
        # Get log retention from config
        log_retention = logs.RetentionDays.ONE_DAY
        
        function = lambda_.Function(
            self,
            'SessionHandler',
            function_name=f'session-http-handler-{self.env_name}',
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler='handler.lambda_handler',
            code=lambda_.Code.from_asset('../lambda/http_session_handler'),
            layers=[self.shared_layer],
            timeout=Duration.seconds(10),
            memory_size=512,
            environment={
                'ENV': self.env_name,
                'SESSIONS_TABLE': self.sessions_table.table_name,
                'CONNECTIONS_TABLE': self.connections_table.table_name,
                'USER_POOL_ID': self.user_pool.user_pool_id,
                'REGION': self.config.get('region', 'us-east-1'),
            },
            log_retention=log_retention,
        )
        
        # Grant DynamoDB permissions
        self.sessions_table.grant_read_write_data(function)
        self.connections_table.grant_read_write_data(function)
        
        # Grant CloudWatch Metrics permissions
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=['cloudwatch:PutMetricData'],
                resources=['*']
            )
        )
        
        # Grant KVS Signaling Channel permissions
        function.add_to_role_policy(
            iam.PolicyStatement(
                sid='KVSSignalingChannelManagement',
                actions=[
                    'kinesisvideo:CreateSignalingChannel',
                    'kinesisvideo:DeleteSignalingChannel',
                    'kinesisvideo:DescribeSignalingChannel',
                    'kinesisvideo:GetSignalingChannelEndpoint',
                    'kinesisvideo:UpdateSignalingChannel',
                    'kinesisvideo:TagResource',
                    'kinesisvideo:GetIceServerConfig',
                ],
                resources=[
                    f'arn:aws:kinesisvideo:{self.region}:{self.account}:channel/session-*/*'
                ]
            )
        )
        
        return function
    
    def _create_http_api(self) -> apigwv2.CfnApi:
        """Create HTTP API Gateway using stable CDK constructs."""
        api = apigwv2.CfnApi(
            self,
            'SessionHttpApi',
            name=f'session-management-http-api-{self.env_name}',
            description='HTTP API for session management CRUD operations',
            protocol_type='HTTP',
            cors_configuration=apigwv2.CfnApi.CorsProperty(
                allow_origins=['*'],  # Configure for production
                allow_methods=['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
                allow_headers=['Content-Type', 'Authorization'],
                max_age=3600,
            ),
        )
        
        return api
    
    def _create_jwt_authorizer(self) -> apigwv2.CfnAuthorizer:
        """Create JWT authorizer using Cognito User Pool."""
        authorizer = apigwv2.CfnAuthorizer(
            self,
            'JwtAuthorizer',
            api_id=self.http_api.ref,
            authorizer_type='JWT',
            name=f'session-jwt-authorizer-{self.env_name}',
            identity_source=['$request.header.Authorization'],
            jwt_configuration=apigwv2.CfnAuthorizer.JWTConfigurationProperty(
                issuer=f'https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool.user_pool_id}',
                audience=[self.config.get('cognitoClientId', '')],
            ),
        )
        
        return authorizer
    
    def _add_routes(self):
        """Add HTTP routes to the API using stable CDK constructs."""
        # Create Lambda integration
        integration = apigwv2.CfnIntegration(
            self,
            'SessionHandlerIntegration',
            api_id=self.http_api.ref,
            integration_type='AWS_PROXY',
            integration_uri=f'arn:aws:apigateway:{self.region}:lambda:path/2015-03-31/functions/{self.session_handler.function_arn}/invocations',
            payload_format_version='2.0',
            timeout_in_millis=10000,
        )
        
        # Grant API Gateway permission to invoke Lambda
        self.session_handler.add_permission(
            'HttpApiInvokePermission',
            principal=iam.ServicePrincipal('apigateway.amazonaws.com'),
            source_arn=f'arn:aws:execute-api:{self.region}:{self.account}:{self.http_api.ref}/*',
        )
        
        # POST /sessions - Create session (requires authentication)
        apigwv2.CfnRoute(
            self,
            'CreateSessionRoute',
            api_id=self.http_api.ref,
            route_key='POST /sessions',
            authorization_type='JWT',
            authorizer_id=self.jwt_authorizer.ref,
            target=f'integrations/{integration.ref}',
        )
        
        # GET /sessions/{sessionId} - Get session (public, no auth required)
        apigwv2.CfnRoute(
            self,
            'GetSessionRoute',
            api_id=self.http_api.ref,
            route_key='GET /sessions/{sessionId}',
            target=f'integrations/{integration.ref}',
        )
        
        # PATCH /sessions/{sessionId} - Update session (requires authentication)
        apigwv2.CfnRoute(
            self,
            'UpdateSessionRoute',
            api_id=self.http_api.ref,
            route_key='PATCH /sessions/{sessionId}',
            authorization_type='JWT',
            authorizer_id=self.jwt_authorizer.ref,
            target=f'integrations/{integration.ref}',
        )
        
        # DELETE /sessions/{sessionId} - Delete session (requires authentication)
        apigwv2.CfnRoute(
            self,
            'DeleteSessionRoute',
            api_id=self.http_api.ref,
            route_key='DELETE /sessions/{sessionId}',
            authorization_type='JWT',
            authorizer_id=self.jwt_authorizer.ref,
            target=f'integrations/{integration.ref}',
        )
        
        # GET /health - Health check (public, no auth required)
        apigwv2.CfnRoute(
            self,
            'HealthCheckRoute',
            api_id=self.http_api.ref,
            route_key='GET /health',
            target=f'integrations/{integration.ref}',
        )
        
        # Create stage for the API
        apigwv2.CfnStage(
            self,
            'HttpApiStage',
            api_id=self.http_api.ref,
            stage_name='$default',
            auto_deploy=True,
        )
    
    def _create_outputs(self):
        """Create CloudFormation outputs."""
        CfnOutput(
            self,
            'HttpApiEndpoint',
            value=f'https://{self.http_api.ref}.execute-api.{self.region}.amazonaws.com',
            description='HTTP API endpoint URL',
            export_name=f'SessionHttpApiEndpoint-{self.env_name}',
        )
        
        CfnOutput(
            self,
            'HttpApiId',
            value=self.http_api.ref,
            description='HTTP API ID',
            export_name=f'SessionHttpApiId-{self.env_name}',
        )
        
        CfnOutput(
            self,
            'SessionHandlerFunctionName',
            value=self.session_handler.function_name,
            description='Session Handler Lambda function name',
        )
        
        CfnOutput(
            self,
            'SessionHandlerFunctionArn',
            value=self.session_handler.function_arn,
            description='Session Handler Lambda function ARN',
        )
