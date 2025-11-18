# HTTP + WebSocket Hybrid Architecture - Design Document

## Overview

This design document outlines the technical approach for implementing an HTTP + WebSocket hybrid architecture that separates stateless session management from stateful real-time communication. The design addresses the architectural mismatch between WebSocket request/response patterns and API Gateway's connection lifecycle by using HTTP for CRUD operations and WebSocket exclusively for bidirectional audio streaming.

### Goals

1. Separate session management (HTTP) from real-time communication (WebSocket)
2. Improve reliability by persisting sessions independently of WebSocket connections
3. Follow AWS best practices for REST APIs and WebSocket APIs
4. Maintain backward compatibility with existing WebSocket session creation
5. Achieve performance targets: HTTP <2s, WebSocket <1s, audio <100ms latency
6. Implement comprehensive error handling and retry logic

### Non-Goals

1. Changing the session data model or DynamoDB schema
2. Modifying the audio transcription or translation pipeline
3. Implementing new session features beyond CRUD operations
4. Changing the authentication mechanism (Cognito JWT remains)
5. Migrating existing sessions (new architecture for new sessions only)

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend Application                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │ SessionHttp      │         │ WebSocketClient  │             │
│  │ Service          │         │                  │             │
│  │                  │         │                  │             │
│  │ - createSession()│         │ - connect()      │             │
│  │ - getSession()   │         │ - sendAudio()    │             │
│  │ - updateSession()│         │ - disconnect()   │             │
│  │ - deleteSession()│         │                  │             │
│  └────────┬─────────┘         └────────┬─────────┘             │
│           │                            │                        │
└───────────┼────────────────────────────┼────────────────────────┘
            │                            │
            │ HTTPS + JWT                │ WSS + JWT
            │                            │
┌───────────▼────────────────────────────▼────────────────────────┐
│                      AWS API Gateway                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────┐      ┌──────────────────────┐         │
│  │  HTTP REST API      │      │  WebSocket API       │         │
│  │                     │      │                      │         │
│  │  POST   /sessions   │      │  $connect            │         │
│  │  GET    /sessions/  │      │  $disconnect         │         │
│  │         {id}        │      │  sendAudio           │         │
│  │  PATCH  /sessions/  │      │  heartbeat           │         │
│  │         {id}        │      │                      │         │
│  │  DELETE /sessions/  │      │                      │         │
│  │         {id}        │      │                      │         │
│  └──────────┬──────────┘      └──────────┬───────────┘         │
│             │                            │                      │
└─────────────┼────────────────────────────┼──────────────────────┘
              │                            │
              │                            │
┌─────────────▼────────────────────────────▼──────────────────────┐
│                      Lambda Functions                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────┐      ┌──────────────────────┐         │
│  │ Session Handler     │      │ Connection Handler   │         │
│  │                     │      │                      │         │
│  │ - create_session()  │      │ - handle_connect()   │         │
│  │ - get_session()     │      │ - handle_disconnect()│         │
│  │ - update_session()  │      │ - handle_audio()     │         │
│  │ - delete_session()  │      │ - handle_heartbeat() │         │
│  └──────────┬──────────┘      └──────────┬───────────┘         │
│             │                            │                      │
└─────────────┼────────────────────────────┼──────────────────────┘
              │                            │
              └────────────┬───────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                      DynamoDB Tables                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Sessions Table                  Connections Table               │
│  PK: sessionId                   PK: connectionId                │
│  - speakerId                     GSI: sessionId-index            │
│  - sourceLanguage                - sessionId                     │
│  - qualityTier                   - targetLanguage                │
│  - status                        - connectionType                │
│  - createdAt                     - connectedAt                   │
│  - ttl                           - ttl                           │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```


### Sequence Diagrams

#### Session Creation Flow (HTTP)

```
┌──────────┐    ┌────────────┐    ┌─────────────┐    ┌──────────┐
│ Frontend │    │ HTTP API   │    │ Session     │    │ DynamoDB │
│          │    │ Gateway    │    │ Handler     │    │          │
└────┬─────┘    └─────┬──────┘    └──────┬──────┘    └────┬─────┘
     │                │                   │                │
     │ POST /sessions │                   │                │
     │ + JWT token    │                   │                │
     ├───────────────>│                   │                │
     │                │                   │                │
     │                │ Validate JWT      │                │
     │                │ (API Gateway      │                │
     │                │  Authorizer)      │                │
     │                │                   │                │
     │                │ Invoke Lambda     │                │
     │                ├──────────────────>│                │
     │                │                   │                │
     │                │                   │ Generate       │
     │                │                   │ session ID     │
     │                │                   │                │
     │                │                   │ PutItem        │
     │                │                   ├───────────────>│
     │                │                   │                │
     │                │                   │ Success        │
     │                │                   │<───────────────┤
     │                │                   │                │
     │                │ 201 Created       │                │
     │                │ {sessionId, ...}  │                │
     │                │<──────────────────┤                │
     │                │                   │                │
     │ Session created│                   │                │
     │<───────────────┤                   │                │
     │                │                   │                │
```

#### WebSocket Connection Flow (With Existing Session)

```
┌──────────┐    ┌────────────┐    ┌─────────────┐    ┌──────────┐
│ Frontend │    │ WebSocket  │    │ Connection  │    │ DynamoDB │
│          │    │ API Gateway│    │ Handler     │    │          │
└────┬─────┘    └─────┬──────┘    └──────┬──────┘    └────┬─────┘
     │                │                   │                │
     │ WSS connect    │                   │                │
     │ ?sessionId=xyz │                   │                │
     │ &token=jwt     │                   │                │
     ├───────────────>│                   │                │
     │                │                   │                │
     │                │ $connect          │                │
     │                │ Validate JWT      │                │
     │                │ (Authorizer)      │                │
     │                │                   │                │
     │                │ Invoke Lambda     │                │
     │                ├──────────────────>│                │
     │                │                   │                │
     │                │                   │ GetItem        │
     │                │                   │ (sessionId)    │
     │                │                   ├───────────────>│
     │                │                   │                │
     │                │                   │ Session data   │
     │                │                   │<───────────────┤
     │                │                   │                │
     │                │                   │ Verify status  │
     │                │                   │ = active       │
     │                │                   │                │
     │                │                   │ PutItem        │
     │                │                   │ (connection)   │
     │                │                   ├───────────────>│
     │                │                   │                │
     │                │ Allow connection  │                │
     │                │<──────────────────┤                │
     │                │                   │                │
     │ Connected      │                   │                │
     │<───────────────┤                   │                │
     │                │                   │                │
```


#### Audio Streaming Flow

```
┌──────────┐    ┌────────────┐    ┌─────────────┐    ┌──────────┐
│ Frontend │    │ WebSocket  │    │ Connection  │    │ Audio    │
│          │    │ API Gateway│    │ Handler     │    │ Pipeline │
└────┬─────┘    └─────┬──────┘    └──────┬──────┘    └────┬─────┘
     │                │                   │                │
     │ sendAudio      │                   │                │
     │ (binary data)  │                   │                │
     ├───────────────>│                   │                │
     │                │                   │                │
     │                │ Route to handler  │                │
     │                ├──────────────────>│                │
     │                │                   │                │
     │                │                   │ Validate       │
     │                │                   │ session active │
     │                │                   │                │
     │                │                   │ Forward audio  │
     │                │                   ├───────────────>│
     │                │                   │                │
     │                │                   │ Processing...  │
     │                │                   │                │
     │                │ Audio received    │                │
     │                │<──────────────────┤                │
     │                │                   │                │
     │ Ack            │                   │                │
     │<───────────────┤                   │                │
     │                │                   │                │
```

## Components and Interfaces

### 1. SessionHttpService (Frontend)

**Purpose**: Handle all HTTP-based session management operations.

**Interface**:

```typescript
interface SessionConfig {
  sourceLanguage: string;
  qualityTier: 'standard' | 'premium';
}

interface SessionMetadata {
  sessionId: string;
  speakerId: string;
  sourceLanguage: string;
  qualityTier: string;
  status: 'active' | 'paused' | 'ended';
  listenerCount: number;
  createdAt: number;
  updatedAt: number;
}

interface SessionUpdateRequest {
  status?: 'active' | 'paused' | 'ended';
  sourceLanguage?: string;
  qualityTier?: 'standard' | 'premium';
}

class SessionHttpService {
  private readonly apiBaseUrl: string;
  private readonly authService: CognitoAuthService;
  
  constructor(apiBaseUrl: string, authService: CognitoAuthService) {
    this.apiBaseUrl = apiBaseUrl;
    this.authService = authService;
  }
  
  async createSession(config: SessionConfig): Promise<SessionMetadata> {
    const token = await this.getValidToken();
    
    const response = await fetch(`${this.apiBaseUrl}/sessions`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    });
    
    if (!response.ok) {
      throw await this.handleHttpError(response);
    }
    
    return response.json();
  }
  
  async getSession(sessionId: string): Promise<SessionMetadata> {
    const response = await fetch(`${this.apiBaseUrl}/sessions/${sessionId}`, {
      method: 'GET',
    });
    
    if (!response.ok) {
      throw await this.handleHttpError(response);
    }
    
    return response.json();
  }
  
  async updateSession(
    sessionId: string,
    updates: SessionUpdateRequest
  ): Promise<SessionMetadata> {
    const token = await this.getValidToken();
    
    const response = await fetch(`${this.apiBaseUrl}/sessions/${sessionId}`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    });
    
    if (!response.ok) {
      throw await this.handleHttpError(response);
    }
    
    return response.json();
  }
  
  async deleteSession(sessionId: string): Promise<void> {
    const token = await this.getValidToken();
    
    const response = await fetch(`${this.apiBaseUrl}/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    
    if (!response.ok) {
      throw await this.handleHttpError(response);
    }
  }
  
  private async getValidToken(): Promise<string> {
    const tokens = TokenStorage.getInstance().getTokens();
    
    if (!tokens) {
      throw new Error('No authentication tokens found');
    }
    
    // Check if token needs refresh
    const timeUntilExpiry = tokens.expiresAt - Date.now();
    if (timeUntilExpiry < 5 * 60 * 1000) {
      const newTokens = await this.authService.refreshTokens();
      TokenStorage.getInstance().storeTokens(newTokens);
      return newTokens.idToken;
    }
    
    return tokens.idToken;
  }
  
  private async handleHttpError(response: Response): Promise<Error> {
    const body = await response.json().catch(() => ({}));
    
    const errorMap: Record<number, string> = {
      400: 'Invalid request parameters',
      401: 'Authentication required',
      403: 'Not authorized to perform this action',
      404: 'Session not found',
      409: 'Session already exists',
      500: 'Internal server error',
      503: 'Service temporarily unavailable',
    };
    
    const message = body.message || errorMap[response.status] || 'Unknown error';
    const error = new Error(message);
    (error as any).statusCode = response.status;
    (error as any).body = body;
    
    return error;
  }
}
```


### 2. Session Handler Lambda (Backend)

**Purpose**: Handle HTTP CRUD operations for sessions.

**Implementation**:

```python
# session-management/lambda/http_session_handler/handler.py

import json
import logging
import os
from typing import Dict, Any
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

from shared.models.session import Session
from shared.data_access.sessions_repository import SessionsRepository
from shared.utils.session_id_generator import SessionIdGenerator
from shared.utils.validators import validate_language_code, validate_quality_tier

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
sessions_table = dynamodb.Table(os.environ['SESSIONS_TABLE_NAME'])
sessions_repo = SessionsRepository(sessions_table)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    HTTP API Lambda handler for session CRUD operations.
    
    Routes:
    - POST /sessions -> create_session
    - GET /sessions/{sessionId} -> get_session
    - PATCH /sessions/{sessionId} -> update_session
    - DELETE /sessions/{sessionId} -> delete_session
    """
    try:
        http_method = event['requestContext']['http']['method']
        path = event['requestContext']['http']['path']
        
        # Extract user ID from JWT claims (added by authorizer)
        user_id = event['requestContext']['authorizer']['jwt']['claims']['sub']
        
        # Route to appropriate handler
        if http_method == 'POST' and path == '/sessions':
            return create_session(event, user_id)
        elif http_method == 'GET' and '/sessions/' in path:
            session_id = path.split('/')[-1]
            return get_session(session_id)
        elif http_method == 'PATCH' and '/sessions/' in path:
            session_id = path.split('/')[-1]
            return update_session(event, session_id, user_id)
        elif http_method == 'DELETE' and '/sessions/' in path:
            session_id = path.split('/')[-1]
            return delete_session(session_id, user_id)
        else:
            return error_response(404, 'Not found')
            
    except Exception as e:
        logger.error(f'Unhandled error: {str(e)}', exc_info=True)
        return error_response(500, 'Internal server error')


def create_session(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Create a new session."""
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        source_language = body.get('sourceLanguage')
        quality_tier = body.get('qualityTier', 'standard')
        
        # Validate inputs
        if not source_language:
            return error_response(400, 'sourceLanguage is required')
        
        validate_language_code(source_language)
        validate_quality_tier(quality_tier)
        
        # Generate unique session ID
        session_id = SessionIdGenerator.generate()
        
        # Create session record
        now = int(datetime.utcnow().timestamp() * 1000)
        ttl = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        
        session_data = {
            'sessionId': session_id,
            'speakerId': user_id,
            'sourceLanguage': source_language,
            'qualityTier': quality_tier,
            'status': 'active',
            'listenerCount': 0,
            'createdAt': now,
            'updatedAt': now,
            'ttl': ttl,
        }
        
        sessions_repo.create_session(session_data)
        
        logger.info(
            f'Session created successfully',
            extra={
                'session_id': session_id,
                'speaker_id': user_id,
                'source_language': source_language,
            }
        )
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps(session_data),
        }
        
    except ValueError as e:
        return error_response(400, str(e))
    except ClientError as e:
        logger.error(f'DynamoDB error: {str(e)}')
        return error_response(500, 'Failed to create session')


def get_session(session_id: str) -> Dict[str, Any]:
    """Retrieve session details."""
    try:
        session = sessions_repo.get_session(session_id)
        
        if not session:
            return error_response(404, 'Session not found')
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps(session),
        }
        
    except ClientError as e:
        logger.error(f'DynamoDB error: {str(e)}')
        return error_response(500, 'Failed to retrieve session')


def update_session(
    event: Dict[str, Any],
    session_id: str,
    user_id: str
) -> Dict[str, Any]:
    """Update session details."""
    try:
        # Get existing session
        session = sessions_repo.get_session(session_id)
        
        if not session:
            return error_response(404, 'Session not found')
        
        # Verify ownership
        if session['speakerId'] != user_id:
            return error_response(403, 'Not authorized to update this session')
        
        # Parse updates
        body = json.loads(event.get('body', '{}'))
        updates = {}
        
        if 'status' in body:
            if body['status'] not in ['active', 'paused', 'ended']:
                return error_response(400, 'Invalid status value')
            updates['status'] = body['status']
        
        if 'sourceLanguage' in body:
            validate_language_code(body['sourceLanguage'])
            updates['sourceLanguage'] = body['sourceLanguage']
        
        if 'qualityTier' in body:
            validate_quality_tier(body['qualityTier'])
            updates['qualityTier'] = body['qualityTier']
        
        if not updates:
            return error_response(400, 'No valid updates provided')
        
        # Update session
        updates['updatedAt'] = int(datetime.utcnow().timestamp() * 1000)
        updated_session = sessions_repo.update_session(session_id, updates)
        
        logger.info(
            f'Session updated successfully',
            extra={
                'session_id': session_id,
                'updates': list(updates.keys()),
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps(updated_session),
        }
        
    except ValueError as e:
        return error_response(400, str(e))
    except ClientError as e:
        logger.error(f'DynamoDB error: {str(e)}')
        return error_response(500, 'Failed to update session')


def delete_session(session_id: str, user_id: str) -> Dict[str, Any]:
    """Delete (end) a session."""
    try:
        # Get existing session
        session = sessions_repo.get_session(session_id)
        
        if not session:
            return error_response(404, 'Session not found')
        
        # Verify ownership
        if session['speakerId'] != user_id:
            return error_response(403, 'Not authorized to delete this session')
        
        # Mark session as ended (soft delete)
        sessions_repo.update_session(session_id, {
            'status': 'ended',
            'updatedAt': int(datetime.utcnow().timestamp() * 1000),
        })
        
        # TODO: Disconnect all WebSocket connections for this session
        # This will be implemented in the connection handler
        
        logger.info(
            f'Session deleted successfully',
            extra={'session_id': session_id}
        )
        
        return {
            'statusCode': 204,
            'headers': {
                'Access-Control-Allow-Origin': '*',
            },
        }
        
    except ClientError as e:
        logger.error(f'DynamoDB error: {str(e)}')
        return error_response(500, 'Failed to delete session')


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Generate error response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({
            'error': message,
            'timestamp': int(datetime.utcnow().timestamp() * 1000),
        }),
    }
```


### 3. Updated Connection Handler (WebSocket)

**Purpose**: Handle WebSocket connections with existing sessions.

**Key Changes**:

```python
# session-management/lambda/connection_handler/handler.py

def handle_connect(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle WebSocket $connect event.
    Requires sessionId in query parameters.
    """
    try:
        connection_id = event['requestContext']['connectionId']
        query_params = event.get('queryStringParameters', {})
        
        # Extract sessionId from query parameters
        session_id = query_params.get('sessionId')
        
        if not session_id:
            logger.error('Missing sessionId in connection request')
            return {'statusCode': 400}
        
        # Verify session exists and is active
        session = sessions_repo.get_session(session_id)
        
        if not session:
            logger.error(f'Session not found: {session_id}')
            return {'statusCode': 404}
        
        if session['status'] != 'active':
            logger.error(f'Session not active: {session_id}, status: {session["status"]}')
            return {'statusCode': 403}
        
        # Store connection with session reference
        connection_data = {
            'connectionId': connection_id,
            'sessionId': session_id,
            'connectionType': 'speaker',  # or 'listener'
            'connectedAt': int(datetime.utcnow().timestamp() * 1000),
            'ttl': int((datetime.utcnow() + timedelta(hours=3)).timestamp()),
        }
        
        connections_repo.create_connection(connection_data)
        
        logger.info(
            'WebSocket connected',
            extra={
                'connection_id': connection_id,
                'session_id': session_id,
            }
        )
        
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f'Connection error: {str(e)}', exc_info=True)
        return {'statusCode': 500}
```

### 4. HTTP API Infrastructure (CDK)

**Purpose**: Define HTTP API Gateway and Lambda resources.

**Implementation**:

```python
# session-management/infrastructure/stacks/http_api_stack.py

from aws_cdk import (
    Stack,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_logs as logs,
    Duration,
)
from constructs import Construct


class HttpApiStack(Stack):
    """CDK stack for HTTP API Gateway and session management."""
    
    def __init__(
        self,
        scope: Construct,
        id: str,
        sessions_table,
        connections_table,
        user_pool,
        **kwargs
    ):
        super().__init__(scope, id, **kwargs)
        
        # Create Lambda function for session handler
        session_handler = lambda_.Function(
            self,
            'SessionHandler',
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler='handler.lambda_handler',
            code=lambda_.Code.from_asset('lambda/http_session_handler'),
            environment={
                'SESSIONS_TABLE_NAME': sessions_table.table_name,
                'CONNECTIONS_TABLE_NAME': connections_table.table_name,
                'USER_POOL_ID': user_pool.user_pool_id,
            },
            timeout=Duration.seconds(10),
            memory_size=512,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )
        
        # Grant DynamoDB permissions
        sessions_table.grant_read_write_data(session_handler)
        connections_table.grant_read_write_data(session_handler)
        
        # Create HTTP API
        http_api = apigwv2.HttpApi(
            self,
            'SessionHttpApi',
            api_name='session-management-http-api',
            description='HTTP API for session management',
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
        
        # Create JWT authorizer
        authorizer = authorizers.HttpJwtAuthorizer(
            'JwtAuthorizer',
            f'https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}',
            identity_source=['$request.header.Authorization'],
        )
        
        # Create Lambda integration
        integration = integrations.HttpLambdaIntegration(
            'SessionHandlerIntegration',
            session_handler,
        )
        
        # Add routes
        http_api.add_routes(
            path='/sessions',
            methods=[apigwv2.HttpMethod.POST],
            integration=integration,
            authorizer=authorizer,
        )
        
        http_api.add_routes(
            path='/sessions/{sessionId}',
            methods=[
                apigwv2.HttpMethod.GET,
                apigwv2.HttpMethod.PATCH,
                apigwv2.HttpMethod.DELETE,
            ],
            integration=integration,
            authorizer=authorizer,
        )
        
        # Output API endpoint
        self.api_endpoint = http_api.url
```


## Data Models

### Session Model (Unchanged)

```python
@dataclass
class Session:
    """Session data model."""
    session_id: str
    speaker_id: str
    source_language: str
    quality_tier: str
    status: str  # 'active', 'paused', 'ended'
    listener_count: int
    created_at: int  # Unix timestamp (milliseconds)
    updated_at: int  # Unix timestamp (milliseconds)
    ttl: int  # Unix timestamp (seconds) for DynamoDB TTL
```

### Connection Model (Enhanced)

```python
@dataclass
class Connection:
    """WebSocket connection data model."""
    connection_id: str
    session_id: str  # Reference to session
    connection_type: str  # 'speaker' or 'listener'
    target_language: Optional[str]  # For listeners only
    connected_at: int  # Unix timestamp (milliseconds)
    ttl: int  # Unix timestamp (seconds) for DynamoDB TTL
```

## Error Handling

### HTTP Error Responses

```typescript
interface HttpErrorResponse {
  error: string;
  timestamp: number;
  details?: Record<string, any>;
}

// Example error responses
{
  "error": "Invalid request parameters",
  "timestamp": 1699500000000,
  "details": {
    "field": "sourceLanguage",
    "message": "Language code must be ISO 639-1 format"
  }
}
```

### Error Handling Strategy

**Frontend**:
1. **5xx errors**: Retry with exponential backoff (3 attempts)
2. **4xx errors**: Show user-friendly message, no retry
3. **Network errors**: Show connectivity message, retry when online
4. **Timeout errors**: Show timeout message, allow manual retry

**Backend**:
1. **Validation errors**: Return 400 with specific field errors
2. **Authentication errors**: Return 401 with clear message
3. **Authorization errors**: Return 403 with ownership message
4. **Not found errors**: Return 404 with resource type
5. **Server errors**: Return 500 with generic message, log details

## Testing Strategy

### Unit Testing

**Frontend (SessionHttpService)**:
- Test createSession with valid config
- Test createSession with invalid config
- Test getSession with existing session
- Test getSession with non-existent session
- Test updateSession with valid updates
- Test updateSession without ownership
- Test deleteSession with ownership
- Test deleteSession without ownership
- Test token refresh before requests
- Test error handling for all HTTP status codes

**Backend (Session Handler Lambda)**:
- Test create_session with valid input
- Test create_session with invalid language
- Test create_session with missing fields
- Test get_session with existing session
- Test get_session with non-existent session
- Test update_session with ownership
- Test update_session without ownership
- Test delete_session with ownership
- Test delete_session without ownership
- Test DynamoDB error handling

### Integration Testing

**HTTP API**:
- Test end-to-end session creation flow
- Test JWT authentication and authorization
- Test CORS headers
- Test rate limiting (if implemented)
- Test concurrent session creation

**WebSocket with HTTP**:
- Test session creation via HTTP, then WebSocket connection
- Test WebSocket connection with non-existent session
- Test WebSocket connection with ended session
- Test audio streaming after HTTP session creation
- Test session update while WebSocket connected

### Performance Testing

**Targets**:
- HTTP session creation: <2s (p95)
- HTTP session retrieval: <500ms (p95)
- HTTP session update: <1s (p95)
- WebSocket connection: <1s (p95)

**Load Testing**:
- 100 concurrent session creations
- 1000 concurrent session retrievals
- 100 concurrent WebSocket connections


## Security Considerations

### Authentication

**HTTP API**:
- JWT authorizer validates token signature using Cognito JWKS
- Token expiration checked automatically
- User ID extracted from JWT claims for authorization

**WebSocket API**:
- Existing Lambda authorizer validates JWT
- Session ID required in query parameters
- Session ownership verified on connection

### Authorization

**Session Ownership**:
- Only session creator (speaker) can update or delete
- Session ID is public (listeners need it to join)
- Listener count is public information

**Data Access**:
- Speakers can only access their own sessions
- Listeners can access any active session by ID
- No PII stored in session records

### Rate Limiting

**Considerations**:
- API Gateway has built-in throttling (10,000 requests/second)
- Consider per-user rate limits for session creation
- Implement exponential backoff on client side

## Monitoring and Observability

### CloudWatch Metrics

**Custom Metrics**:
- `SessionCreationCount` - Number of sessions created
- `SessionCreationDuration` - Time to create session
- `SessionRetrievalDuration` - Time to retrieve session
- `SessionUpdateDuration` - Time to update session
- `SessionDeletionCount` - Number of sessions deleted
- `WebSocketConnectionCount` - Active WebSocket connections
- `WebSocketConnectionDuration` - Time to establish connection

**Dimensions**:
- `Environment` (dev, staging, prod)
- `Region`
- `SourceLanguage`
- `QualityTier`

### CloudWatch Logs

**Structured Logging**:
```json
{
  "timestamp": "2025-11-18T12:34:56.789Z",
  "level": "INFO",
  "operation": "create_session",
  "session_id": "golden-eagle-427",
  "speaker_id": "user-123",
  "source_language": "en",
  "duration_ms": 145,
  "request_id": "abc-123-def"
}
```

### CloudWatch Alarms

**Critical Alarms**:
- HTTP API error rate >5% (5 minutes)
- HTTP API latency p95 >2s (5 minutes)
- WebSocket connection failure rate >5% (5 minutes)
- Lambda function errors >10 (5 minutes)

**Warning Alarms**:
- HTTP API latency p95 >1s (10 minutes)
- Session creation rate spike (>2x normal)
- DynamoDB throttling events

## Deployment Strategy

### Phase 1: Infrastructure Deployment

1. Deploy HTTP API Gateway
2. Deploy Session Handler Lambda
3. Configure JWT authorizer
4. Test HTTP endpoints in dev

**Validation**:
- HTTP API accessible
- JWT authentication works
- Session CRUD operations work
- Logs and metrics flowing

### Phase 2: Frontend Integration

1. Implement SessionHttpService
2. Update SessionCreationOrchestrator to use HTTP
3. Keep WebSocket for audio streaming
4. Test in dev environment

**Validation**:
- Session creation via HTTP works
- WebSocket connection with sessionId works
- Audio streaming works
- Error handling works

### Phase 3: Staging Deployment

1. Deploy to staging environment
2. Run integration tests
3. Run performance tests
4. Monitor for 24 hours

**Validation**:
- All tests passing
- Performance targets met
- No errors in logs
- Metrics look healthy

### Phase 4: Production Deployment

1. Deploy to production (blue/green)
2. Monitor closely for 1 hour
3. Gradually increase traffic
4. Full rollout after 24 hours

**Rollback Plan**:
- Keep old WebSocket session creation active
- Can switch frontend back to WebSocket
- No data migration needed

## Migration Path

### Backward Compatibility

**Old Flow (WebSocket Session Creation)**:
```
Frontend → WebSocket → createSession message → Session created
```

**New Flow (HTTP Session Creation)**:
```
Frontend → HTTP POST /sessions → Session created
Frontend → WebSocket (with sessionId) → Audio streaming
```

**Both flows supported simultaneously**

### Feature Flag

```typescript
// Frontend configuration
const USE_HTTP_SESSION_CREATION = 
  import.meta.env.VITE_USE_HTTP_SESSION_CREATION === 'true';

if (USE_HTTP_SESSION_CREATION) {
  // Use SessionHttpService
  const session = await sessionHttpService.createSession(config);
  await wsClient.connect({ sessionId: session.sessionId });
} else {
  // Use old WebSocket session creation
  await wsClient.connect();
  await wsClient.send({ action: 'createSession', ...config });
}
```

### Deprecation Timeline

1. **Week 1-2**: Deploy HTTP API, test in dev
2. **Week 3-4**: Enable for 10% of users in production
3. **Week 5-6**: Enable for 50% of users
4. **Week 7-8**: Enable for 100% of users
5. **Week 9+**: Monitor usage of old endpoint
6. **Month 3**: Deprecate old WebSocket session creation

## Performance Optimization

### HTTP API Optimization

**Lambda Cold Start**:
- Use provisioned concurrency for session handler (if needed)
- Optimize Lambda package size
- Reuse AWS SDK clients

**DynamoDB Optimization**:
- Use consistent reads only when necessary
- Batch operations where possible
- Monitor for throttling

### WebSocket Optimization

**Connection Pooling**:
- Reuse WebSocket connections
- Implement connection refresh before 2-hour limit
- Handle reconnection gracefully

**Message Batching**:
- Batch small audio chunks if possible
- Use binary format for audio data
- Compress data if beneficial

## Cost Considerations

### HTTP API Costs

**API Gateway**:
- $1.00 per million requests
- Estimated: 1M sessions/month = $1.00

**Lambda**:
- $0.20 per 1M requests
- $0.0000166667 per GB-second
- Estimated: 1M sessions × 200ms × 512MB = $1.70

**Total HTTP API**: ~$2.70/month for 1M sessions

### Comparison with WebSocket

**WebSocket Session Creation**:
- Connection cost: $0.25 per million minutes
- Message cost: $1.00 per million messages
- Estimated: Higher due to connection overhead

**HTTP Session Creation**:
- Lower cost for session creation
- WebSocket only for audio streaming
- Better cost efficiency

## Success Criteria

### Functional Success

- [ ] Sessions can be created via HTTP POST
- [ ] Sessions can be retrieved via HTTP GET
- [ ] Sessions can be updated via HTTP PATCH
- [ ] Sessions can be deleted via HTTP DELETE
- [ ] WebSocket connects with existing sessionId
- [ ] Audio streaming works over WebSocket
- [ ] Old WebSocket session creation still works

### Performance Success

- [ ] HTTP session creation <2s (p95)
- [ ] HTTP session retrieval <500ms (p95)
- [ ] HTTP session update <1s (p95)
- [ ] WebSocket connection <1s (p95)
- [ ] Audio streaming latency <100ms (p95)

### Quality Success

- [ ] Test coverage >80% for new code
- [ ] Zero critical bugs in staging
- [ ] Error handling comprehensive
- [ ] Logging and monitoring complete
- [ ] Documentation updated

### Production Readiness

- [ ] All P0 requirements completed
- [ ] Security review passed
- [ ] Performance benchmarks met
- [ ] Rollback plan tested
- [ ] Monitoring configured and tested
