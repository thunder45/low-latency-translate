"""
End-to-end integration tests for WebSocket API.

Tests complete workflows including:
- Speaker session lifecycle (create, heartbeat, disconnect)
- Listener lifecycle (join, receive messages, disconnect)
- Multi-listener scenarios
- Connection refresh for long sessions
- Speaker disconnect notifications
"""
import json
import time
from unittest.mock import Mock, patch
import pytest
from moto import mock_dynamodb
import boto3


@pytest.fixture
def mock_api_gateway_client():
    """Mock API Gateway Management API client."""
    client = Mock()
    client.post_to_connection = Mock(return_value={})
    return client


@pytest.fixture
def mock_boto3_clients(mock_api_gateway_client):
    """Mock all boto3 clients used in handlers. Returns tuple of (client_factory, api_gateway_mock)."""
    def client_factory(service_name, **kwargs):
        if service_name == 'apigatewaymanagementapi':
            return mock_api_gateway_client
        elif service_name == 'cloudwatch':
            mock_cw = Mock()
            mock_cw.put_metric_data = Mock(return_value={})
            return mock_cw
        elif service_name == 'translate':
            mock_translate = Mock()
            mock_translate.list_languages = Mock(return_value={
                'Languages': [
                    {'LanguageCode': 'en'},
                    {'LanguageCode': 'es'},
                    {'LanguageCode': 'fr'}
                ]
            })
            return mock_translate
        elif service_name == 'polly':
            mock_polly = Mock()
            mock_polly.describe_voices = Mock(return_value={
                'Voices': [
                    {'LanguageCode': 'en-US'},
                    {'LanguageCode': 'es-ES'},
                    {'LanguageCode': 'fr-FR'}
                ]
            })
            return mock_polly
        else:
            return Mock()
    
    return client_factory, mock_api_gateway_client


@pytest.fixture
def setup_handlers(env_vars, aws_credentials):
    """Set up handler modules with proper environment."""
    import sys
    import os
    import importlib
    
    # Clear any cached imports
    modules_to_remove = [k for k in sys.modules.keys() if 'handler' in k]
    for mod in modules_to_remove:
        del sys.modules[mod]
    
    # Import handlers after environment is set
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'connection_handler'))
    import handler as connection_handler
    sys.path.pop(0)
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'heartbeat_handler'))
    import handler as heartbeat_handler
    sys.path.pop(0)
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'disconnect_handler'))
    import handler as disconnect_handler
    sys.path.pop(0)
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'refresh_handler'))
    import handler as refresh_handler
    sys.path.pop(0)
    
    return {
        'connection': connection_handler,
        'heartbeat': heartbeat_handler,
        'disconnect': disconnect_handler,
        'refresh': refresh_handler
    }


@pytest.fixture
def dynamodb_tables(aws_credentials, env_vars):
    """Create DynamoDB tables for testing."""
    with mock_dynamodb():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create Sessions table
        sessions_table = dynamodb.create_table(
            TableName='Sessions-test',
            KeySchema=[{'AttributeName': 'sessionId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'sessionId', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create Connections table with GSI
        connections_table = dynamodb.create_table(
            TableName='Connections-test',
            KeySchema=[{'AttributeName': 'connectionId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[
                {'AttributeName': 'connectionId', 'AttributeType': 'S'},
                {'AttributeName': 'sessionId', 'AttributeType': 'S'},
                {'AttributeName': 'targetLanguage', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': 'sessionId-targetLanguage-index',
                'KeySchema': [
                    {'AttributeName': 'sessionId', 'KeyType': 'HASH'},
                    {'AttributeName': 'targetLanguage', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create RateLimits table
        rate_limits_table = dynamodb.create_table(
            TableName='RateLimits-test',
            KeySchema=[{'AttributeName': 'identifier', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'identifier', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        yield sessions_table, connections_table, rate_limits_table


class TestSpeakerSessionLifecycle:
    """Test complete speaker session lifecycle."""
    
    def test_complete_speaker_flow_create_heartbeat_disconnect(
        self,
        dynamodb_tables,
        mock_boto3_clients,
        setup_handlers
    ):
        """
        Test complete speaker flow:
        1. Create session via $connect
        2. Send heartbeat
        3. Disconnect via $disconnect
        4. Verify cleanup
        """
        # Setup
        sessions_table, connections_table, rate_limits_table = dynamodb_tables
        mock_boto3_clients, mock_api_gateway_client = mock_boto3_clients
        handlers = setup_handlers
        connection_id = 'speaker-conn-123'
        user_id = 'user-123'
        
        # Step 1: Create session ($connect)
        connect_event = {
            'requestContext': {
                'connectionId': connection_id,
                'eventType': 'CONNECT',
                'authorizer': {
                    'userId': user_id,
                    'email': 'speaker@example.com'
                }
            },
            'queryStringParameters': {
                'action': 'createSession',
                'sourceLanguage': 'en',
                'qualityTier': 'standard'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            connect_response = handlers['connection'].lambda_handler(connect_event, {})
        
        assert connect_response['statusCode'] == 200
        body = json.loads(connect_response['body'])
        assert body['type'] == 'sessionCreated'
        session_id = body['sessionId']
        
        # Verify session in DynamoDB
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['isActive'] is True
        assert session['speakerUserId'] == user_id
        assert session['listenerCount'] == 0
        
        # Step 2: Send heartbeat
        heartbeat_event = {
            'requestContext': {
                'connectionId': connection_id,
                'routeKey': 'heartbeat',
                'eventType': 'MESSAGE',
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test'
            },
            'body': json.dumps({
                'action': 'heartbeat',
                'timestamp': int(time.time() * 1000)
            })
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            heartbeat_response = handlers['heartbeat'].lambda_handler(heartbeat_event, {})
        
        assert heartbeat_response['statusCode'] == 200
        
        # Verify heartbeatAck was sent
        mock_api_gateway_client.post_to_connection.assert_called()
        call_args = mock_api_gateway_client.post_to_connection.call_args
        assert call_args[1]['ConnectionId'] == connection_id
        message = json.loads(call_args[1]['Data'])
        assert message['type'] == 'heartbeatAck'
        
        # Step 3: Disconnect ($disconnect)
        disconnect_event = {
            'requestContext': {
                'connectionId': connection_id,
                'eventType': 'DISCONNECT'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            disconnect_response = handlers['disconnect'].lambda_handler(disconnect_event, {})
        
        assert disconnect_response['statusCode'] == 200
        
        # Step 4: Verify cleanup
        # Session should be marked inactive
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['isActive'] is False
        
        # Connection should be deleted
        conn_response = connections_table.get_item(Key={'connectionId': connection_id})
        assert 'Item' not in conn_response


class TestListenerLifecycle:
    """Test complete listener lifecycle."""
    
    def test_complete_listener_flow_join_receive_disconnect(
        self,
        dynamodb_tables,
        mock_boto3_clients,
        setup_handlers
    ):
        """
        Test complete listener flow:
        1. Join active session
        2. Receive messages
        3. Disconnect
        4. Verify count decrement
        """
        # Setup
        sessions_table, connections_table, rate_limits_table = dynamodb_tables
        mock_boto3_clients, mock_api_gateway_client = mock_boto3_clients
        handlers = setup_handlers
        
        # Create active session first (using valid session ID format)
        session_id = 'faithful-shepherd-123'
        speaker_conn_id = 'speaker-conn-123'
        sessions_table.put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': speaker_conn_id,
            'speakerUserId': 'speaker-user-123',
            'sourceLanguage': 'en',
            'isActive': True,
            'listenerCount': 0,
            'qualityTier': 'standard',
            'createdAt': int(time.time() * 1000),
            'expiresAt': int(time.time()) + 7200
        })
        
        # Step 1: Listener joins
        listener_conn_id = 'listener-conn-456'
        join_event = {
            'requestContext': {
                'connectionId': listener_conn_id,
                'eventType': 'CONNECT'
            },
            'queryStringParameters': {
                'action': 'joinSession',
                'sessionId': session_id,
                'targetLanguage': 'es'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            join_response = handlers['connection'].lambda_handler(join_event, {})
        
        assert join_response['statusCode'] == 200
        body = json.loads(join_response['body'])
        assert body['type'] == 'sessionJoined'
        assert body['sessionId'] == session_id
        
        # Verify listener count incremented
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['listenerCount'] == 1
        
        # Verify connection record created
        connection = connections_table.get_item(Key={'connectionId': listener_conn_id})['Item']
        assert connection['sessionId'] == session_id
        assert connection['targetLanguage'] == 'es'
        assert connection['role'] == 'listener'
        
        # Step 2: Send heartbeat (receive messages)
        heartbeat_event = {
            'requestContext': {
                'connectionId': listener_conn_id,
                'routeKey': 'heartbeat',
                'eventType': 'MESSAGE',
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            heartbeat_response = handlers['heartbeat'].lambda_handler(heartbeat_event, {})
        
        assert heartbeat_response['statusCode'] == 200
        
        # Step 3: Disconnect
        disconnect_event = {
            'requestContext': {
                'connectionId': listener_conn_id,
                'eventType': 'DISCONNECT'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            disconnect_response = handlers['disconnect'].lambda_handler(disconnect_event, {})
        
        assert disconnect_response['statusCode'] == 200
        
        # Step 4: Verify count decremented
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['listenerCount'] == 0
        
        # Connection should be deleted
        conn_response = connections_table.get_item(Key={'connectionId': listener_conn_id})
        assert 'Item' not in conn_response


class TestMultiListenerScenario:
    """Test scenarios with multiple concurrent listeners."""
    
    def test_100_concurrent_listeners(
        self,
        dynamodb_tables,
        mock_boto3_clients,
        setup_handlers
    ):
        """
        Test 100 listeners joining same session:
        1. Create session
        2. Join 100 listeners
        3. Verify all connections active
        4. Speaker disconnects
        5. Verify all listeners notified
        """
        # Setup
        sessions_table, connections_table, rate_limits_table = dynamodb_tables
        mock_boto3_clients, mock_api_gateway_client = mock_boto3_clients
        handlers = setup_handlers
        
        # Create active session (using valid session ID format)
        session_id = 'blessed-temple-456'
        speaker_conn_id = 'speaker-conn-multi'
        sessions_table.put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': speaker_conn_id,
            'speakerUserId': 'speaker-user-multi',
            'sourceLanguage': 'en',
            'isActive': True,
            'listenerCount': 0,
            'qualityTier': 'standard',
            'createdAt': int(time.time() * 1000),
            'expiresAt': int(time.time()) + 7200
        })
        
        # Add speaker connection
        connections_table.put_item(Item={
            'connectionId': speaker_conn_id,
            'sessionId': session_id,
            'role': 'speaker',
            'connectedAt': int(time.time() * 1000),
            'ttl': int(time.time()) + 7200
        })
        
        # Join 100 listeners
        listener_conn_ids = []
        for i in range(100):
            listener_conn_id = f'listener-conn-{i}'
            listener_conn_ids.append(listener_conn_id)
            
            join_event = {
                'requestContext': {
                    'connectionId': listener_conn_id,
                    'eventType': 'CONNECT'
                },
                'queryStringParameters': {
                    'action': 'joinSession',
                    'sessionId': session_id,
                    'targetLanguage': 'es'
                }
            }
            
            with patch('boto3.client', side_effect=mock_boto3_clients):
                join_response = handlers['connection'].lambda_handler(join_event, {})
            
            assert join_response['statusCode'] == 200
        
        # Verify listener count
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['listenerCount'] == 100
        
        # Verify all connections exist
        for conn_id in listener_conn_ids:
            connection = connections_table.get_item(Key={'connectionId': conn_id})
            assert 'Item' in connection
        
        # Speaker disconnects
        disconnect_event = {
            'requestContext': {
                'connectionId': speaker_conn_id,
                'eventType': 'DISCONNECT'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            disconnect_response = handlers['disconnect'].lambda_handler(disconnect_event, {})
        
        assert disconnect_response['statusCode'] == 200
        
        # Verify session marked inactive
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['isActive'] is False
        
        # Verify all listeners were notified (sessionEnded message sent)
        # Should have 100 calls to post_to_connection
        assert mock_api_gateway_client.post_to_connection.call_count >= 100
        
        # Verify all listener connections deleted
        for conn_id in listener_conn_ids:
            conn_response = connections_table.get_item(Key={'connectionId': conn_id})
            assert 'Item' not in conn_response


class TestConnectionRefreshLongSessions:
    """Test connection refresh for sessions longer than 2 hours."""
    
    def test_speaker_connection_refresh_at_100_minutes(
        self,
        dynamodb_tables,
        mock_boto3_clients,
        setup_handlers
    ):
        """
        Test speaker connection refresh:
        1. Create session
        2. Simulate 100 minutes passing
        3. Send heartbeat (triggers refresh message)
        4. Establish new connection with refreshConnection
        5. Verify speakerConnectionId updated
        """
        # Setup
        sessions_table, connections_table, rate_limits_table = dynamodb_tables
        mock_boto3_clients, mock_api_gateway_client = mock_boto3_clients
        handlers = setup_handlers
        
        # Create session (using valid session ID format)
        session_id = 'gracious-prophet-789'
        old_conn_id = 'speaker-old-conn'
        user_id = 'speaker-user-refresh'
        
        sessions_table.put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': old_conn_id,
            'speakerUserId': user_id,
            'sourceLanguage': 'en',
            'isActive': True,
            'listenerCount': 0,
            'qualityTier': 'standard',
            'createdAt': int(time.time() * 1000),
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create connection record with 100-minute-old timestamp
        connection_time = int((time.time() - 100 * 60) * 1000)  # 100 minutes ago
        connections_table.put_item(Item={
            'connectionId': old_conn_id,
            'sessionId': session_id,
            'role': 'speaker',
            'connectedAt': connection_time,
            'ttl': int(time.time()) + 7200
        })
        
        # Send heartbeat (should trigger refresh message)
        heartbeat_event = {
            'requestContext': {
                'connectionId': old_conn_id,
                'routeKey': 'heartbeat',
                'eventType': 'MESSAGE',
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            heartbeat_response = handlers['heartbeat'].lambda_handler(heartbeat_event, {})
        
        assert heartbeat_response['statusCode'] == 200
        
        # Verify connectionRefreshRequired message was sent
        calls = mock_api_gateway_client.post_to_connection.call_args_list
        refresh_message_sent = False
        for call in calls:
            if 'Data' in call[1]:
                message = json.loads(call[1]['Data'])
                if message.get('type') == 'connectionRefreshRequired':
                    refresh_message_sent = True
                    assert message['sessionId'] == session_id
                    assert message['role'] == 'speaker'
        
        assert refresh_message_sent, "connectionRefreshRequired message should be sent"
        
        # Establish new connection with refreshConnection
        new_conn_id = 'speaker-new-conn'
        refresh_event = {
            'requestContext': {
                'connectionId': new_conn_id,
                'eventType': 'CONNECT',
                'authorizer': {
                    'userId': user_id
                }
            },
            'queryStringParameters': {
                'action': 'refreshConnection',
                'sessionId': session_id,
                'role': 'speaker'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            refresh_response = handlers['refresh'].lambda_handler(refresh_event, {})
        
        assert refresh_response['statusCode'] == 200
        
        # Verify speakerConnectionId updated
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['speakerConnectionId'] == new_conn_id
        
        # Verify connectionRefreshComplete message sent
        calls = mock_api_gateway_client.post_to_connection.call_args_list
        complete_message_sent = False
        for call in calls:
            if 'Data' in call[1]:
                message = json.loads(call[1]['Data'])
                if message.get('type') == 'connectionRefreshComplete':
                    complete_message_sent = True
                    assert message['sessionId'] == session_id
                    assert message['role'] == 'speaker'
        
        assert complete_message_sent, "connectionRefreshComplete message should be sent"
    
    def test_listener_connection_refresh_at_100_minutes(
        self,
        dynamodb_tables,
        mock_boto3_clients,
        setup_handlers
    ):
        """
        Test listener connection refresh:
        1. Listener joins session
        2. Simulate 100 minutes passing
        3. Send heartbeat (triggers refresh message)
        4. Establish new connection with refreshConnection
        5. Verify new connection created and count managed
        """
        # Setup
        sessions_table, connections_table, rate_limits_table = dynamodb_tables
        mock_boto3_clients, mock_api_gateway_client = mock_boto3_clients
        handlers = setup_handlers
        
        # Create active session (using valid session ID format)
        session_id = 'merciful-psalm-234'
        sessions_table.put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': 'speaker-conn',
            'speakerUserId': 'speaker-user',
            'sourceLanguage': 'en',
            'isActive': True,
            'listenerCount': 1,
            'qualityTier': 'standard',
            'createdAt': int(time.time() * 1000),
            'expiresAt': int(time.time()) + 7200
        })
        
        # Create listener connection with 100-minute-old timestamp
        old_listener_conn = 'listener-old-conn'
        connection_time = int((time.time() - 100 * 60) * 1000)  # 100 minutes ago
        connections_table.put_item(Item={
            'connectionId': old_listener_conn,
            'sessionId': session_id,
            'targetLanguage': 'es',
            'role': 'listener',
            'connectedAt': connection_time,
            'ttl': int(time.time()) + 7200
        })
        
        # Send heartbeat (should trigger refresh message)
        heartbeat_event = {
            'requestContext': {
                'connectionId': old_listener_conn,
                'routeKey': 'heartbeat',
                'eventType': 'MESSAGE',
                'domainName': 'test.execute-api.us-east-1.amazonaws.com',
                'stage': 'test'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            heartbeat_response = handlers['heartbeat'].lambda_handler(heartbeat_event, {})
        
        assert heartbeat_response['statusCode'] == 200
        
        # Establish new connection with refreshConnection
        new_listener_conn = 'listener-new-conn'
        refresh_event = {
            'requestContext': {
                'connectionId': new_listener_conn,
                'eventType': 'CONNECT'
            },
            'queryStringParameters': {
                'action': 'refreshConnection',
                'sessionId': session_id,
                'targetLanguage': 'es',
                'role': 'listener'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            refresh_response = handlers['refresh'].lambda_handler(refresh_event, {})
        
        assert refresh_response['statusCode'] == 200
        
        # Verify new connection created
        new_connection = connections_table.get_item(Key={'connectionId': new_listener_conn})['Item']
        assert new_connection['sessionId'] == session_id
        assert new_connection['targetLanguage'] == 'es'
        
        # Verify listener count temporarily increased (both connections exist)
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['listenerCount'] == 2  # Temporary spike during transition
        
        # Old connection disconnects
        disconnect_event = {
            'requestContext': {
                'connectionId': old_listener_conn,
                'eventType': 'DISCONNECT'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            disconnect_response = handlers['disconnect'].lambda_handler(disconnect_event, {})
        
        assert disconnect_response['statusCode'] == 200
        
        # Verify count back to 1
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['listenerCount'] == 1


class TestSpeakerDisconnectNotifications:
    """Test that all listeners are notified when speaker disconnects."""
    
    def test_speaker_disconnect_notifies_all_listeners(
        self,
        dynamodb_tables,
        mock_boto3_clients,
        setup_handlers
    ):
        """
        Test speaker disconnect notifications:
        1. Create session with multiple listeners
        2. Speaker disconnects
        3. Verify all listeners receive sessionEnded message
        4. Verify all connections cleaned up
        """
        # Setup
        sessions_table, connections_table, rate_limits_table = dynamodb_tables
        mock_boto3_clients, mock_api_gateway_client = mock_boto3_clients
        handlers = setup_handlers
        
        # Create session (using valid session ID format)
        session_id = 'joyful-grace-567'
        speaker_conn_id = 'speaker-notify-conn'
        sessions_table.put_item(Item={
            'sessionId': session_id,
            'speakerConnectionId': speaker_conn_id,
            'speakerUserId': 'speaker-notify-user',
            'sourceLanguage': 'en',
            'isActive': True,
            'listenerCount': 5,
            'qualityTier': 'standard',
            'createdAt': int(time.time() * 1000),
            'expiresAt': int(time.time()) + 7200
        })
        
        # Add speaker connection
        connections_table.put_item(Item={
            'connectionId': speaker_conn_id,
            'sessionId': session_id,
            'role': 'speaker',
            'connectedAt': int(time.time() * 1000),
            'ttl': int(time.time()) + 7200
        })
        
        # Add 5 listener connections
        listener_conn_ids = []
        for i in range(5):
            conn_id = f'listener-notify-{i}'
            listener_conn_ids.append(conn_id)
            connections_table.put_item(Item={
                'connectionId': conn_id,
                'sessionId': session_id,
                'targetLanguage': 'es',
                'role': 'listener',
                'connectedAt': int(time.time() * 1000),
                'ttl': int(time.time()) + 7200
            })
        
        # Speaker disconnects
        disconnect_event = {
            'requestContext': {
                'connectionId': speaker_conn_id,
                'eventType': 'DISCONNECT'
            }
        }
        
        with patch('boto3.client', side_effect=mock_boto3_clients):
            disconnect_response = handlers['disconnect'].lambda_handler(disconnect_event, {})
        
        assert disconnect_response['statusCode'] == 200
        
        # Verify session marked inactive
        session = sessions_table.get_item(Key={'sessionId': session_id})['Item']
        assert session['isActive'] is False
        
        # Verify sessionEnded messages sent to all listeners
        calls = mock_api_gateway_client.post_to_connection.call_args_list
        session_ended_calls = []
        for call in calls:
            if 'Data' in call[1]:
                message = json.loads(call[1]['Data'])
                if message.get('type') == 'sessionEnded':
                    session_ended_calls.append(call[1]['ConnectionId'])
        
        # Should have sent sessionEnded to all 5 listeners
        assert len(session_ended_calls) == 5
        for conn_id in listener_conn_ids:
            assert conn_id in session_ended_calls
        
        # Verify all connections deleted
        for conn_id in listener_conn_ids:
            conn_response = connections_table.get_item(Key={'connectionId': conn_id})
            assert 'Item' not in conn_response
        
        speaker_response = connections_table.get_item(Key={'connectionId': speaker_conn_id})
        assert 'Item' not in speaker_response
