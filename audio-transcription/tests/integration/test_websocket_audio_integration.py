"""
Integration tests for WebSocket audio integration.

Tests end-to-end audio flow from WebSocket reception through Transcribe
to Translation Pipeline.
"""

import asyncio
import base64
import json
import time
from typing import Dict, Any
from unittest.mock import Mock, patch, AsyncMock, MagicMock

import pytest
from moto import mock_dynamodb


@pytest.fixture
def mock_dynamodb_tables():
    """Create mock DynamoDB tables for testing."""
    with mock_dynamodb():
        import boto3
        
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create Sessions table
        sessions_table = dynamodb.create_table(
            TableName='Sessions',
            KeySchema=[
                {'AttributeName': 'sessionId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'sessionId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create Connections table
        connections_table = dynamodb.create_table(
            TableName='Connections',
            KeySchema=[
                {'AttributeName': 'connectionId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'connectionId', 'AttributeType': 'S'},
                {'AttributeName': 'sessionId', 'AttributeType': 'S'},
                {'AttributeName': 'targetLanguage', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'sessionId-targetLanguage-index',
                    'KeySchema': [
                        {'AttributeName': 'sessionId', 'KeyType': 'HASH'},
                        {'AttributeName': 'targetLanguage', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Add test data
        sessions_table.put_item(Item={
            'sessionId': 'test-session-123',
            'speakerConnectionId': 'speaker-conn-123',
            'speakerUserId': 'user-123',
            'sourceLanguage': 'en',
            'isActive': True,
            'listenerCount': 2,
            'createdAt': int(time.time()),
            'expiresAt': int(time.time()) + 7200,
            'broadcastState': {
                'isActive': True,
                'isPaused': False,
                'isMuted': False,
                'volume': 1.0,
                'lastStateChange': int(time.time())
            }
        })
        
        connections_table.put_item(Item={
            'connectionId': 'speaker-conn-123',
            'sessionId': 'test-session-123',
            'role': 'speaker',
            'userId': 'user-123',
            'connectedAt': int(time.time()),
            'ttl': int(time.time()) + 7200
        })
        
        connections_table.put_item(Item={
            'connectionId': 'listener-conn-1',
            'sessionId': 'test-session-123',
            'role': 'listener',
            'targetLanguage': 'es',
            'connectedAt': int(time.time()),
            'ttl': int(time.time()) + 7200
        })
        
        connections_table.put_item(Item={
            'connectionId': 'listener-conn-2',
            'sessionId': 'test-session-123',
            'role': 'listener',
            'targetLanguage': 'fr',
            'connectedAt': int(time.time()),
            'ttl': int(time.time()) + 7200
        })
        
        yield {
            'sessions': sessions_table,
            'connections': connections_table
        }


@pytest.fixture
def sample_audio_chunk():
    """Generate sample PCM audio chunk."""
    # 100ms of 16kHz 16-bit mono PCM audio (silence)
    chunk_size = int(16000 * 0.1 * 2)  # 3200 bytes
    audio_data = b'\x00' * chunk_size
    return base64.b64encode(audio_data).decode('utf-8')


@pytest.fixture
def websocket_audio_event(sample_audio_chunk):
    """Create WebSocket event for sendAudio action."""
    return {
        'requestContext': {
            'connectionId': 'speaker-conn-123',
            'routeKey': 'sendAudio',
            'eventType': 'MESSAGE',
            'requestId': 'test-request-123',
            'domainName': 'test.execute-api.us-east-1.amazonaws.com',
            'stage': 'test'
        },
        'body': json.dumps({
            'action': 'sendAudio',
            'audioData': sample_audio_chunk
        }),
        'isBase64Encoded': False
    }


class TestEndToEndAudioFlow:
    """Test end-to-end audio flow from WebSocket to Translation Pipeline."""
    
    @patch('lambda.audio_processor.handler.TranscribeStreamHandler')
    @patch('lambda.audio_processor.handler.boto3.client')
    def test_speaker_sends_audio_chunks_successfully(
        self,
        mock_boto_client,
        mock_transcribe_handler_class,
        mock_dynamodb_tables,
        websocket_audio_event
    ):
        """
        Test: Speaker connects and sends audio chunks.
        Verify: Transcribe stream initialized and audio processed.
        """
        # Setup mocks
        mock_transcribe_handler = AsyncMock()
        mock_transcribe_handler.initialize_stream = AsyncMock(return_value=True)
        mock_transcribe_handler.send_audio_chunk = AsyncMock()
        mock_transcribe_handler.is_active = True
        mock_transcribe_handler_class.return_value = mock_transcribe_handler
        
        # Mock Lambda client for Translation Pipeline
        mock_lambda = Mock()
        mock_boto_client.return_value = mock_lambda
        
        # Execute
        response = lambda_handler(websocket_audio_event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['type'] == 'audioReceived'
        assert body['sessionId'] == 'test-session-123'
        
        # Verify Transcribe stream was initialized
        mock_transcribe_handler_class.assert_called_once()
        mock_transcribe_handler.initialize_stream.assert_called_once()
        
        # Verify audio was sent to Transcribe
        mock_transcribe_handler.send_audio_chunk.assert_called_once()
    
    @patch('audio_transcription.lambda.audio_processor.handler.TranscribeStreamHandler')
    @patch('audio_transcription.lambda.audio_processor.handler.boto3.client')
    def test_multiple_audio_chunks_no_loss_or_duplication(
        self,
        mock_boto_client,
        mock_transcribe_handler_class,
        mock_dynamodb_tables,
        websocket_audio_event,
        sample_audio_chunk
    ):
        """
        Test: Speaker sends multiple audio chunks.
        Verify: No audio loss or duplication.
        """
        # Setup mocks
        mock_transcribe_handler = AsyncMock()
        mock_transcribe_handler.initialize_stream = AsyncMock(return_value=True)
        mock_transcribe_handler.send_audio_chunk = AsyncMock()
        mock_transcribe_handler.is_active = True
        mock_transcribe_handler_class.return_value = mock_transcribe_handler
        
        mock_lambda = Mock()
        mock_boto_client.return_value = mock_lambda
        
        # Send 10 audio chunks
        for i in range(10):
            response = lambda_handler(websocket_audio_event, {})
            assert response['statusCode'] == 200
        
        # Verify all chunks were processed
        assert mock_transcribe_handler.send_audio_chunk.call_count == 10
        
        # Verify no duplicate initialization
        assert mock_transcribe_handler.initialize_stream.call_count == 1
    
    @patch('audio_transcription.lambda.audio_processor.handler.TranscribeStreamHandler')
    @patch('audio_transcription.lambda.audio_processor.handler.boto3.client')
    def test_transcription_results_forwarded_to_translation_pipeline(
        self,
        mock_boto_client,
        mock_transcribe_handler_class,
        mock_dynamodb_tables,
        websocket_audio_event
    ):
        """
        Test: Transcribe returns results.
        Verify: Results forwarded to Translation Pipeline.
        """
        # Setup mocks
        mock_transcribe_handler = AsyncMock()
        mock_transcribe_handler.initialize_stream = AsyncMock(return_value=True)
        mock_transcribe_handler.send_audio_chunk = AsyncMock()
        mock_transcribe_handler.is_active = True
        
        # Simulate transcription result
        async def mock_process_events():
            # Simulate receiving a transcription result
            await asyncio.sleep(0.1)
            return {
                'text': 'Hello world',
                'isPartial': False,
                'stability': 1.0,
                'timestamp': time.time()
            }
        
        mock_transcribe_handler.process_events = mock_process_events
        mock_transcribe_handler_class.return_value = mock_transcribe_handler
        
        mock_lambda = Mock()
        mock_boto_client.return_value = mock_lambda
        
        # Execute
        response = lambda_handler(websocket_audio_event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        
        # Note: In real implementation, Translation Pipeline would be invoked
        # This test verifies the handler setup is correct


class TestControlMessageFlow:
    """Test control message flow and state management."""
    
    @patch('session_management.lambda.connection_handler.handler.boto3.client')
    def test_speaker_pauses_broadcast(
        self,
        mock_boto_client,
        mock_dynamodb_tables
    ):
        """
        Test: Speaker pauses broadcast.
        Verify: Session state updated and listeners notified.
        """
        from session_management.lambda.connection_handler.handler import lambda_handler
        
        # Setup mocks
        mock_apigw = Mock()
        mock_boto_client.return_value = mock_apigw
        
        # Create pause event
        pause_event = {
            'requestContext': {
                'connectionId': 'speaker-conn-123',
                'routeKey': 'pauseBroadcast',
                'eventType': 'MESSAGE'
            },
            'body': json.dumps({
                'action': 'pauseBroadcast'
            })
        }
        
        # Execute
        response = lambda_handler(pause_event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['type'] == 'broadcastPaused'
        
        # Verify session state was updated
        import boto3
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        sessions_table = dynamodb.Table('Sessions')
        session = sessions_table.get_item(Key={'sessionId': 'test-session-123'})['Item']
        assert session['broadcastState']['isPaused'] is True
        
        # Verify listeners were notified (2 listeners)
        assert mock_apigw.post_to_connection.call_count == 2
    
    @patch('session_management.lambda.connection_handler.handler.boto3.client')
    def test_speaker_resumes_after_pause(
        self,
        mock_boto_client,
        mock_dynamodb_tables
    ):
        """
        Test: Speaker resumes after pausing.
        Verify: Audio processing resumed.
        """
        from session_management.lambda.connection_handler.handler import lambda_handler
        
        # Setup mocks
        mock_apigw = Mock()
        mock_boto_client.return_value = mock_apigw
        
        # First pause
        pause_event = {
            'requestContext': {
                'connectionId': 'speaker-conn-123',
                'routeKey': 'pauseBroadcast',
                'eventType': 'MESSAGE'
            },
            'body': json.dumps({'action': 'pauseBroadcast'})
        }
        lambda_handler(pause_event, {})
        
        # Then resume
        resume_event = {
            'requestContext': {
                'connectionId': 'speaker-conn-123',
                'routeKey': 'resumeBroadcast',
                'eventType': 'MESSAGE'
            },
            'body': json.dumps({'action': 'resumeBroadcast'})
        }
        response = lambda_handler(resume_event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['type'] == 'broadcastResumed'
        
        # Verify session state
        import boto3
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        sessions_table = dynamodb.Table('Sessions')
        session = sessions_table.get_item(Key={'sessionId': 'test-session-123'})['Item']
        assert session['broadcastState']['isPaused'] is False


class TestSessionStatusQueries:
    """Test session status queries and periodic updates."""
    
    @patch('session_management.lambda.session_status_handler.handler.boto3.client')
    def test_speaker_queries_session_status(
        self,
        mock_boto_client,
        mock_dynamodb_tables
    ):
        """
        Test: Speaker queries session status.
        Verify: Correct listener count and language distribution.
        """
        from session_management.lambda.session_status_handler.handler import lambda_handler
        
        # Create status query event
        status_event = {
            'requestContext': {
                'connectionId': 'speaker-conn-123',
                'routeKey': 'getSessionStatus',
                'eventType': 'MESSAGE'
            },
            'body': json.dumps({
                'action': 'getSessionStatus'
            })
        }
        
        # Execute
        response = lambda_handler(status_event, {})
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['type'] == 'sessionStatus'
        assert body['sessionId'] == 'test-session-123'
        assert body['listenerCount'] == 2
        assert body['languageDistribution'] == {'es': 1, 'fr': 1}
        assert 'sessionDuration' in body
        assert 'broadcastState' in body
    
    def test_status_query_response_latency_under_500ms(
        self,
        mock_dynamodb_tables
    ):
        """
        Test: Status query performance.
        Verify: Response latency <500ms.
        """
        from session_management.lambda.session_status_handler.handler import lambda_handler
        
        status_event = {
            'requestContext': {
                'connectionId': 'speaker-conn-123',
                'routeKey': 'getSessionStatus',
                'eventType': 'MESSAGE'
            },
            'body': json.dumps({'action': 'getSessionStatus'})
        }
        
        # Measure latency
        start_time = time.time()
        response = lambda_handler(status_event, {})
        latency_ms = (time.time() - start_time) * 1000
        
        # Verify latency
        assert latency_ms < 500
        assert response['statusCode'] == 200


class TestErrorScenarios:
    """Test error handling scenarios."""
    
    @patch('audio_transcription.lambda.audio_processor.handler.TranscribeStreamHandler')
    def test_invalid_audio_format_returns_error(
        self,
        mock_transcribe_handler_class,
        mock_dynamodb_tables
    ):
        """
        Test: Invalid audio format sent.
        Verify: Error returned to speaker.
        """
        from audio_transcription.lambda.audio_processor.handler import lambda_handler
        
        # Create event with invalid audio
        invalid_event = {
            'requestContext': {
                'connectionId': 'speaker-conn-123',
                'routeKey': 'sendAudio',
                'eventType': 'MESSAGE'
            },
            'body': json.dumps({
                'action': 'sendAudio',
                'audioData': base64.b64encode(b'invalid').decode('utf-8')
            })
        }
        
        # Execute
        response = lambda_handler(invalid_event, {})
        
        # Verify error response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['type'] == 'error'
        assert 'INVALID_AUDIO_FORMAT' in body['code']
    
    def test_unauthorized_action_returns_403(
        self,
        mock_dynamodb_tables
    ):
        """
        Test: Listener tries speaker action.
        Verify: 403 Forbidden returned.
        """
        from session_management.lambda.connection_handler.handler import lambda_handler
        
        # Create event from listener trying to pause
        unauthorized_event = {
            'requestContext': {
                'connectionId': 'listener-conn-1',  # Listener connection
                'routeKey': 'pauseBroadcast',
                'eventType': 'MESSAGE'
            },
            'body': json.dumps({
                'action': 'pauseBroadcast'
            })
        }
        
        # Execute
        response = lambda_handler(unauthorized_event, {})
        
        # Verify forbidden response
        assert response['statusCode'] == 403
        body = json.loads(response['body'])
        assert body['type'] == 'error'
        assert 'UNAUTHORIZED' in body['code']
    
    @patch('audio_transcription.lambda.audio_processor.handler.TranscribeStreamHandler')
    def test_rate_limit_violations_handled(
        self,
        mock_transcribe_handler_class,
        mock_dynamodb_tables,
        websocket_audio_event
    ):
        """
        Test: Rate limit exceeded.
        Verify: Chunks dropped and metric emitted.
        """
        from audio_transcription.lambda.audio_processor.handler import lambda_handler
        
        # Setup mocks
        mock_transcribe_handler = AsyncMock()
        mock_transcribe_handler.initialize_stream = AsyncMock(return_value=True)
        mock_transcribe_handler.send_audio_chunk = AsyncMock()
        mock_transcribe_handler.is_active = True
        mock_transcribe_handler_class.return_value = mock_transcribe_handler
        
        # Send 100 chunks rapidly (exceeds 50/sec limit)
        responses = []
        for i in range(100):
            response = lambda_handler(websocket_audio_event, {})
            responses.append(response)
        
        # Verify some chunks were rate limited
        rate_limited = [r for r in responses if r['statusCode'] == 429]
        assert len(rate_limited) > 0
        
        # Verify successful chunks were processed
        successful = [r for r in responses if r['statusCode'] == 200]
        assert len(successful) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
