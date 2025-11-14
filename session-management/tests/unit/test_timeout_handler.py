"""
Unit tests for timeout handler.
"""
import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'timeout_handler'))

from handler import (
    send_timeout_message,
    close_connection,
    trigger_disconnect_handler,
    check_and_close_idle_connections,
    lambda_handler
)


class TestSendTimeoutMessage:
    """Test suite for send_timeout_message function."""
    
    @patch('handler.boto3.client')
    def test_send_timeout_message_success(self, mock_boto_client):
        """Test successful timeout message send."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        result = send_timeout_message('conn-123', 'https://api.example.com/prod')
        
        assert result is True
        mock_client.post_to_connection.assert_called_once()
        call_args = mock_client.post_to_connection.call_args
        assert call_args[1]['ConnectionId'] == 'conn-123'
        
        # Verify message structure
        data = json.loads(call_args[1]['Data'].decode('utf-8'))
        assert data['type'] == 'connectionTimeout'
        assert 'message' in data
        assert 'idleSeconds' in data
        assert 'timestamp' in data
    
    @patch('handler.boto3.client')
    def test_send_timeout_message_gone_exception(self, mock_boto_client):
        """Test timeout message send with GoneException."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Create a mock exception that looks like GoneException
        class GoneException(Exception):
            pass
        
        mock_client.post_to_connection.side_effect = GoneException('Connection gone')
        
        result = send_timeout_message('conn-123', 'https://api.example.com/prod')
        
        assert result is False
    
    @patch('handler.boto3.client')
    def test_send_timeout_message_other_error(self, mock_boto_client):
        """Test timeout message send with other error."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.post_to_connection.side_effect = Exception('Network error')
        
        result = send_timeout_message('conn-123', 'https://api.example.com/prod')
        
        assert result is False


class TestCloseConnection:
    """Test suite for close_connection function."""
    
    @patch('handler.boto3.client')
    def test_close_connection_success(self, mock_boto_client):
        """Test successful connection close."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        result = close_connection('conn-123', 'https://api.example.com/prod')
        
        assert result is True
        mock_client.delete_connection.assert_called_once_with(ConnectionId='conn-123')
    
    @patch('handler.boto3.client')
    def test_close_connection_already_gone(self, mock_boto_client):
        """Test close connection when already gone."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        class GoneException(Exception):
            pass
        
        mock_client.delete_connection.side_effect = GoneException('Connection gone')
        
        result = close_connection('conn-123', 'https://api.example.com/prod')
        
        assert result is True  # Already closed is considered success
    
    @patch('handler.boto3.client')
    def test_close_connection_error(self, mock_boto_client):
        """Test close connection with error."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.delete_connection.side_effect = Exception('API error')
        
        result = close_connection('conn-123', 'https://api.example.com/prod')
        
        assert result is False


class TestTriggerDisconnectHandler:
    """Test suite for trigger_disconnect_handler function."""
    
    @patch('handler.boto3.client')
    @patch.dict(os.environ, {'DISCONNECT_HANDLER_FUNCTION': 'DisconnectHandler'})
    def test_trigger_disconnect_handler_success(self, mock_boto_client):
        """Test successful disconnect handler trigger."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        trigger_disconnect_handler('conn-123', 'session-456', 'speaker')
        
        mock_client.invoke.assert_called_once()
        call_args = mock_client.invoke.call_args
        assert call_args[1]['FunctionName'] == 'DisconnectHandler'
        assert call_args[1]['InvocationType'] == 'Event'  # Async
        
        # Verify event structure
        payload = json.loads(call_args[1]['Payload'])
        assert payload['requestContext']['connectionId'] == 'conn-123'
        assert payload['sessionId'] == 'session-456'
        assert payload['role'] == 'speaker'
    
    @patch('handler.boto3.client')
    @patch.dict(os.environ, {'DISCONNECT_HANDLER_FUNCTION': 'DisconnectHandler'})
    def test_trigger_disconnect_handler_error(self, mock_boto_client):
        """Test disconnect handler trigger with error."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.invoke.side_effect = Exception('Lambda error')
        
        # Should not raise exception
        trigger_disconnect_handler('conn-123', 'session-456', 'listener')


class TestCheckAndCloseIdleConnections:
    """Test suite for check_and_close_idle_connections function."""
    
    @patch('handler.connections_repo')
    @patch('handler.send_timeout_message')
    @patch('handler.close_connection')
    @patch('handler.trigger_disconnect_handler')
    @patch('handler.metrics_publisher')
    @patch.dict(os.environ, {'CONNECTION_IDLE_TIMEOUT_SECONDS': '120'})
    def test_check_no_idle_connections(
        self,
        mock_metrics,
        mock_trigger,
        mock_close,
        mock_send,
        mock_repo
    ):
        """Test check with no idle connections."""
        current_time = int(time.time() * 1000)
        
        # All connections are active (recent activity)
        mock_repo.scan_all_connections.return_value = [
            {
                'connectionId': 'conn-1',
                'sessionId': 'session-1',
                'role': 'speaker',
                'lastActivityTime': current_time - 60000  # 60 seconds ago
            },
            {
                'connectionId': 'conn-2',
                'sessionId': 'session-1',
                'role': 'listener',
                'lastActivityTime': current_time - 30000  # 30 seconds ago
            }
        ]
        
        stats = check_and_close_idle_connections('https://api.example.com/prod')
        
        assert stats['checked'] == 2
        assert stats['idle'] == 0
        assert stats['closed'] == 0
        mock_send.assert_not_called()
        mock_close.assert_not_called()
        mock_trigger.assert_not_called()
    
    @patch('handler.connections_repo')
    @patch('handler.send_timeout_message')
    @patch('handler.close_connection')
    @patch('handler.trigger_disconnect_handler')
    @patch('handler.metrics_publisher')
    @patch.dict(os.environ, {'CONNECTION_IDLE_TIMEOUT_SECONDS': '120'})
    def test_check_with_idle_connections(
        self,
        mock_metrics,
        mock_trigger,
        mock_close,
        mock_send,
        mock_repo
    ):
        """Test check with idle connections."""
        current_time = int(time.time() * 1000)
        
        # One idle connection
        mock_repo.scan_all_connections.return_value = [
            {
                'connectionId': 'conn-1',
                'sessionId': 'session-1',
                'role': 'speaker',
                'lastActivityTime': current_time - 180000  # 180 seconds ago (idle)
            },
            {
                'connectionId': 'conn-2',
                'sessionId': 'session-1',
                'role': 'listener',
                'lastActivityTime': current_time - 60000  # 60 seconds ago (active)
            }
        ]
        
        mock_close.return_value = True
        
        stats = check_and_close_idle_connections('https://api.example.com/prod')
        
        assert stats['checked'] == 2
        assert stats['idle'] == 1
        assert stats['closed'] == 1
        assert stats['speaker_timeouts'] == 1
        assert stats['listener_timeouts'] == 0
        
        mock_send.assert_called_once_with('conn-1', 'https://api.example.com/prod')
        mock_close.assert_called_once_with('conn-1', 'https://api.example.com/prod')
        mock_trigger.assert_called_once_with('conn-1', 'session-1', 'speaker')
    
    @patch('handler.connections_repo')
    @patch('handler.send_timeout_message')
    @patch('handler.close_connection')
    @patch('handler.trigger_disconnect_handler')
    @patch('handler.metrics_publisher')
    @patch.dict(os.environ, {'CONNECTION_IDLE_TIMEOUT_SECONDS': '120'})
    def test_check_with_multiple_idle_connections(
        self,
        mock_metrics,
        mock_trigger,
        mock_close,
        mock_send,
        mock_repo
    ):
        """Test check with multiple idle connections."""
        current_time = int(time.time() * 1000)
        
        # Multiple idle connections
        mock_repo.scan_all_connections.return_value = [
            {
                'connectionId': 'conn-1',
                'sessionId': 'session-1',
                'role': 'speaker',
                'lastActivityTime': current_time - 180000  # Idle
            },
            {
                'connectionId': 'conn-2',
                'sessionId': 'session-1',
                'role': 'listener',
                'lastActivityTime': current_time - 200000  # Idle
            },
            {
                'connectionId': 'conn-3',
                'sessionId': 'session-2',
                'role': 'listener',
                'lastActivityTime': current_time - 150000  # Idle
            }
        ]
        
        mock_close.return_value = True
        
        stats = check_and_close_idle_connections('https://api.example.com/prod')
        
        assert stats['checked'] == 3
        assert stats['idle'] == 3
        assert stats['closed'] == 3
        assert stats['speaker_timeouts'] == 1
        assert stats['listener_timeouts'] == 2
    
    @patch('handler.connections_repo')
    @patch('handler.send_timeout_message')
    @patch('handler.close_connection')
    @patch('handler.trigger_disconnect_handler')
    @patch('handler.metrics_publisher')
    @patch.dict(os.environ, {'CONNECTION_IDLE_TIMEOUT_SECONDS': '120'})
    def test_check_uses_connected_at_fallback(
        self,
        mock_metrics,
        mock_trigger,
        mock_close,
        mock_send,
        mock_repo
    ):
        """Test check uses connectedAt when lastActivityTime missing."""
        current_time = int(time.time() * 1000)
        
        # Connection without lastActivityTime (uses connectedAt)
        mock_repo.scan_all_connections.return_value = [
            {
                'connectionId': 'conn-1',
                'sessionId': 'session-1',
                'role': 'speaker',
                'connectedAt': current_time - 180000  # Idle
                # No lastActivityTime
            }
        ]
        
        mock_close.return_value = True
        
        stats = check_and_close_idle_connections('https://api.example.com/prod')
        
        assert stats['idle'] == 1
        assert stats['closed'] == 1


class TestLambdaHandler:
    """Test suite for lambda_handler function."""
    
    @patch('handler.check_and_close_idle_connections')
    @patch('handler.metrics_publisher')
    @patch('handler.API_GATEWAY_ENDPOINT', 'https://api.example.com/prod')
    def test_lambda_handler_success(self, mock_metrics, mock_check):
        """Test successful lambda handler execution."""
        mock_check.return_value = {
            'checked': 10,
            'idle': 2,
            'closed': 2,
            'speaker_timeouts': 1,
            'listener_timeouts': 1
        }
        
        event = {}  # EventBridge scheduled event
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['message'] == 'Timeout check completed'
        assert body['statistics']['checked'] == 10
        assert body['statistics']['idle'] == 2
        assert body['statistics']['closed'] == 2
        
        # Verify metrics were emitted
        assert mock_metrics.emit_metric.call_count == 3
    
    @patch('handler.check_and_close_idle_connections')
    @patch.dict(os.environ, {'CONNECTION_IDLE_TIMEOUT_SECONDS': '120'})
    def test_lambda_handler_missing_endpoint(self, mock_check):
        """Test lambda handler with missing API Gateway endpoint."""
        event = {}
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'endpoint not configured' in body['error']
        mock_check.assert_not_called()
    
    @patch('handler.check_and_close_idle_connections')
    @patch('handler.metrics_publisher')
    @patch.dict(os.environ, {
        'API_GATEWAY_ENDPOINT': 'https://api.example.com/prod',
        'CONNECTION_IDLE_TIMEOUT_SECONDS': '120'
    })
    def test_lambda_handler_error(self, mock_metrics, mock_check):
        """Test lambda handler with error."""
        mock_check.side_effect = Exception('DynamoDB error')
        
        event = {}
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert 'error' in body
