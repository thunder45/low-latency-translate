"""
Unit tests for Heartbeat Handler Lambda.

Tests heartbeat acknowledgment, connection refresh detection, and warning messages.

Requirements: 10, 11, 12
"""
import json
import time
import sys
import os
from unittest.mock import Mock, MagicMock
import pytest
import boto3
from moto import mock_dynamodb
import importlib.util

# Set environment variables for testing
os.environ['CONNECTIONS_TABLE'] = 'Connections-test'
os.environ['CONNECTION_REFRESH_MINUTES'] = '100'
os.environ['CONNECTION_WARNING_MINUTES'] = '105'
os.environ['CONNECTION_MAX_DURATION_HOURS'] = '2'

# Import handler using importlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
handler_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'heartbeat_handler', 'handler.py')
spec = importlib.util.spec_from_file_location('heartbeat_handler', handler_path)
heartbeat_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(heartbeat_handler)

lambda_handler = heartbeat_handler.lambda_handler


@pytest.fixture(scope='function')
def aws_credentials():
    """Mock AWS credentials."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture(scope='function')
def dynamodb_tables(aws_credentials):
    """Create mock DynamoDB tables."""
    with mock_dynamodb():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create Connections table
        connections_table = dynamodb.create_table(
            TableName='Connections-test',
            KeySchema=[
                {'AttributeName': 'connectionId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'connectionId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        yield {'connections': connections_table}


@pytest.fixture
def mock_api_gateway():
    """Mock API Gateway Management API client."""
    mock_client = MagicMock()
    mock_client.post_to_connection = MagicMock()
    
    # Patch boto3.client to return our mock
    original_client = heartbeat_handler.boto3.client
    
    def mock_boto_client(service_name, **kwargs):
        if service_name == 'apigatewaymanagementapi':
            return mock_client
        return original_client(service_name, **kwargs)
    
    heartbeat_handler.boto3.client = mock_boto_client
    
    yield mock_client
    
    # Restore original
    heartbeat_handler.boto3.client = original_client


@pytest.fixture
def heartbeat_event():
    """Create a sample heartbeat event."""
    return {
        'requestContext': {
            'connectionId': 'test-connection-123',
            'domainName': 'test.execute-api.us-east-1.amazonaws.com',
            'stage': 'test',
            'eventType': 'MESSAGE',
            'routeKey': 'heartbeat'
        },
        'body': json.dumps({'action': 'heartbeat'})
    }


class TestHeartbeatAckResponse:
    """Test heartbeat acknowledgment response."""
    
    def test_heartbeat_ack_sent_successfully(
        self,
        mock_api_gateway,
        dynamodb_tables,
        heartbeat_event
    ):
        """Test that heartbeatAck is sent successfully."""
        # Create connection record (50 minutes old)
        current_time = int(time.time() * 1000)
        dynamodb_tables['connections'].put_item(
            Item={
                'connectionId': 'test-connection-123',
                'sessionId': 'test-session-456',
                'role': 'listener',
                'targetLanguage': 'es',
                'connectedAt': current_time - (50 * 60 * 1000),
                'ttl': int(time.time()) + 7200
            }
        )
        
        # Execute
        response = lambda_handler(heartbeat_event, None)
        
        # Verify
        assert response['statusCode'] == 200
        
        # Verify API Gateway client was called
        mock_api_gateway.post_to_connection.assert_called_once()
        
        # Get the call arguments
        call_args = mock_api_gateway.post_to_connection.call_args
        assert call_args[1]['ConnectionId'] == 'test-connection-123'
        
        # Verify message contains heartbeatAck
        sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
        assert sent_data['type'] == 'heartbeatAck'
        assert 'timestamp' in sent_data
    
    def test_heartbeat_ack_sent_even_without_connection_record(
        self,
        mock_api_gateway,
        dynamodb_tables,
        heartbeat_event
    ):
        """Test heartbeatAck sent even if connection not in DB."""
        # No connection record created
        
        # Execute
        response = lambda_handler(heartbeat_event, None)
        
        # Should still send ack
        assert response['statusCode'] == 200
        mock_api_gateway.post_to_connection.assert_called_once()
        
        # Verify it's the ack message
        call_args = mock_api_gateway.post_to_connection.call_args
        sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
        assert sent_data['type'] == 'heartbeatAck'


class TestConnectionRefreshRequired:
    """Test connectionRefreshRequired message at 100-minute threshold."""
    
    def test_connection_refresh_required_at_100_minutes(
        self,
        mock_api_gateway,
        dynamodb_tables,
        heartbeat_event
    ):
        """Test connectionRefreshRequired sent at 100-minute threshold."""
        # Create connection at 100 minutes ago
        current_time = int(time.time() * 1000)
        dynamodb_tables['connections'].put_item(
            Item={
                'connectionId': 'test-connection-123',
                'sessionId': 'test-session-456',
                'role': 'speaker',
                'connectedAt': current_time - (100 * 60 * 1000),  # Exactly 100 minutes
                'ttl': int(time.time()) + 7200
            }
        )
        
        # Execute
        response = lambda_handler(heartbeat_event, None)
        
        # Verify
        assert response['statusCode'] == 200
        
        # Verify two messages were sent (refresh + ack)
        assert mock_api_gateway.post_to_connection.call_count == 2
        
        # Get first call (refresh message)
        first_call = mock_api_gateway.post_to_connection.call_args_list[0]
        refresh_data = json.loads(first_call[1]['Data'].decode('utf-8'))
        
        assert refresh_data['type'] == 'connectionRefreshRequired'
        assert refresh_data['sessionId'] == 'test-session-456'
        assert refresh_data['role'] == 'speaker'
        assert 'message' in refresh_data
    
    def test_connection_refresh_includes_target_language_for_listener(
        self,
        mock_api_gateway,
        dynamodb_tables,
        heartbeat_event
    ):
        """Test connectionRefreshRequired includes targetLanguage for listeners."""
        # Create listener connection at 100 minutes
        current_time = int(time.time() * 1000)
        dynamodb_tables['connections'].put_item(
            Item={
                'connectionId': 'test-connection-123',
                'sessionId': 'test-session-456',
                'role': 'listener',
                'targetLanguage': 'es',
                'connectedAt': current_time - (100 * 60 * 1000),
                'ttl': int(time.time()) + 7200
            }
        )
        
        # Execute
        response = lambda_handler(heartbeat_event, None)
        
        # Verify
        assert response['statusCode'] == 200
        
        # Get refresh message
        first_call = mock_api_gateway.post_to_connection.call_args_list[0]
        refresh_data = json.loads(first_call[1]['Data'].decode('utf-8'))
        
        assert refresh_data['type'] == 'connectionRefreshRequired'
        assert refresh_data['targetLanguage'] == 'es'
    
    def test_no_refresh_message_before_threshold(
        self,
        mock_api_gateway,
        dynamodb_tables,
        heartbeat_event
    ):
        """Test no refresh message sent before 100-minute threshold."""
        # Connection at 50 minutes (well before threshold)
        current_time = int(time.time() * 1000)
        dynamodb_tables['connections'].put_item(
            Item={
                'connectionId': 'test-connection-123',
                'sessionId': 'test-session-456',
                'role': 'listener',
                'targetLanguage': 'es',
                'connectedAt': current_time - (50 * 60 * 1000),
                'ttl': int(time.time()) + 7200
            }
        )
        
        # Execute
        response = lambda_handler(heartbeat_event, None)
        
        # Verify only one message sent (heartbeatAck)
        assert response['statusCode'] == 200
        assert mock_api_gateway.post_to_connection.call_count == 1
        
        # Verify it's the ack message
        call_args = mock_api_gateway.post_to_connection.call_args
        sent_data = json.loads(call_args[1]['Data'].decode('utf-8'))
        assert sent_data['type'] == 'heartbeatAck'


class TestConnectionWarning:
    """Test connectionWarning message at 105-minute threshold."""
    
    def test_connection_warning_at_105_minutes(
        self,
        mock_api_gateway,
        dynamodb_tables,
        heartbeat_event
    ):
        """Test connectionWarning sent at 105-minute threshold."""
        # Create connection at 105 minutes ago
        current_time = int(time.time() * 1000)
        dynamodb_tables['connections'].put_item(
            Item={
                'connectionId': 'test-connection-123',
                'sessionId': 'test-session-456',
                'role': 'listener',
                'connectedAt': current_time - (105 * 60 * 1000),  # 105 minutes
                'ttl': int(time.time()) + 7200
            }
        )
        
        # Execute
        response = lambda_handler(heartbeat_event, None)
        
        # Verify
        assert response['statusCode'] == 200
        
        # Verify two messages sent (warning + ack)
        assert mock_api_gateway.post_to_connection.call_count == 2
        
        # Get first call (warning message)
        first_call = mock_api_gateway.post_to_connection.call_args_list[0]
        warning_data = json.loads(first_call[1]['Data'].decode('utf-8'))
        
        assert warning_data['type'] == 'connectionWarning'
        assert 'remainingMinutes' in warning_data
        # Check remaining minutes is approximately 15 (120 - 105 = 15 minutes)
        remaining = float(warning_data['remainingMinutes'])
        assert 14.9 < remaining < 15.1
    
    def test_no_warning_before_threshold(
        self,
        mock_api_gateway,
        dynamodb_tables,
        heartbeat_event
    ):
        """Test no warning sent before 105-minute threshold."""
        # Connection at 50 minutes
        current_time = int(time.time() * 1000)
        dynamodb_tables['connections'].put_item(
            Item={
                'connectionId': 'test-connection-123',
                'sessionId': 'test-session-456',
                'role': 'listener',
                'connectedAt': current_time - (50 * 60 * 1000),
                'ttl': int(time.time()) + 7200
            }
        )
        
        # Execute
        response = lambda_handler(heartbeat_event, None)
        
        # Verify only one message sent (heartbeatAck)
        assert response['statusCode'] == 200
        assert mock_api_gateway.post_to_connection.call_count == 1


class TestGoneExceptionHandling:
    """Test handling of GoneException for disconnected clients."""
    
    def test_gone_exception_returns_410(
        self,
        mock_api_gateway,
        dynamodb_tables,
        heartbeat_event
    ):
        """Test GoneException returns 410 status."""
        # Create connection record
        current_time = int(time.time() * 1000)
        dynamodb_tables['connections'].put_item(
            Item={
                'connectionId': 'test-connection-123',
                'sessionId': 'test-session-456',
                'role': 'listener',
                'connectedAt': current_time - (50 * 60 * 1000),
                'ttl': int(time.time()) + 7200
            }
        )
        
        # Setup API client to raise GoneException
        mock_api_gateway.exceptions.GoneException = type('GoneException', (Exception,), {})
        mock_api_gateway.post_to_connection.side_effect = mock_api_gateway.exceptions.GoneException()
        
        # Execute
        response = lambda_handler(heartbeat_event, None)
        
        # Verify 410 Gone status
        assert response['statusCode'] == 410


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_missing_connection_id_returns_400(
        self,
        mock_api_gateway,
        dynamodb_tables
    ):
        """Test missing connectionId returns 400."""
        # Event without connectionId
        invalid_event = {
            'requestContext': {
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test'
            }
        }
        
        response = lambda_handler(invalid_event, None)
        
        assert response['statusCode'] == 400
