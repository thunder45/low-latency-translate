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
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
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
        
        return function
    
    def _create_http_api(self) -> apigwv2.HttpApi:
        """Create HTTP API Gateway with CORS configuration."""
        api = apigwv2.HttpApi(
            self,
            'SessionHttpApi',
            api_name=f'session-management-http-api-{self.env_name}',
            description='HTTP API for session management CRUD operations',
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=['*'],  # Configure for production
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.PATCH,
                    apigwv2.CorsHttpMethod.DELETE,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_headers=['Content-Type', 'Authorization'],
                max_age=Duration.hours(1),
            ),
        )
        
        return api
    
    def _create_jwt_authorizer(self) -> authorizers.HttpJwtAuthorizer:
        """Create JWT authorizer using Cognito User Pool."""
        authorizer = authorizers.HttpJwtAuthorizer(
            'JwtAuthorizer',
            f'https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool.user_pool_id}',
            identity_source=['$request.header.Authorization'],
            jwt_audience=[self.config.get('cognitoClientId', '')],
        )
        
        return authorizer
    
    def _add_routes(self):
        """Add HTTP routes to the API."""
        # Create Lambda integration
        integration = integrations.HttpLambdaIntegration(
            'SessionHandlerIntegration',
            self.session_handler,
        )
        
        # POST /sessions - Create session (requires authentication)
        self.http_api.add_routes(
            path='/sessions',
            methods=[apigwv2.HttpMethod.POST],
            integration=integration,
            authorizer=self.jwt_authorizer,
        )
        
        # GET /sessions/{sessionId} - Get session (public, no auth required)
        self.http_api.add_routes(
            path='/sessions/{sessionId}',
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )
        
        # PATCH /sessions/{sessionId} - Update session (requires authentication)
        self.http_api.add_routes(
            path='/sessions/{sessionId}',
            methods=[apigwv2.HttpMethod.PATCH],
            integration=integration,
            authorizer=self.jwt_authorizer,
        )
        
        # DELETE /sessions/{sessionId} - Delete session (requires authentication)
        self.http_api.add_routes(
            path='/sessions/{sessionId}',
            methods=[apigwv2.HttpMethod.DELETE],
            integration=integration,
            authorizer=self.jwt_authorizer,
        )
        
        # GET /health - Health check (public, no auth required)
        self.http_api.add_routes(
            path='/health',
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )
    
    def _create_outputs(self):
        """Create CloudFormation outputs."""
        CfnOutput(
            self,
            'HttpApiEndpoint',
            value=self.http_api.url or '',
            description='HTTP API endpoint URL',
            export_name=f'SessionHttpApiEndpoint-{self.env_name}',
        )
        
        CfnOutput(
            self,
            'HttpApiId',
            value=self.http_api.http_api_id,
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
