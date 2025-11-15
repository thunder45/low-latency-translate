"""
Unit tests for Lambda Translation Pipeline client.

Tests cover:
- Successful invocation with mock Lambda client
- Retry logic with transient failures
- Failure after max retries
- Payload construction with all required fields
- Default emotion values when not provided
- Asynchronous invocation (InvocationType='Event')
- Correct payload format matching Translation Pipeline expectations
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError
from shared.services.lambda_translation_pipeline import LambdaTranslationPipeline


class TestLambdaTranslationPipeline:
    """Test suite for LambdaTranslationPipeline."""
    
    @pytest.fixture
    def mock_lambda_client(self):
        """Create mock Lambda client."""
        return Mock()
    
    @pytest.fixture
    def pipeline(self, mock_lambda_client):
        """Create LambdaTranslationPipeline instance with mock client."""
        return LambdaTranslationPipeline(
            function_name='TestTranslationFunction',
            lambda_client=mock_lambda_client
        )
    
    def test_initialization(self, pipeline):
        """Test pipeline initialization."""
        assert pipeline.function_name == 'TestTranslationFunction'
        assert pipeline.max_retries == 2
        assert pipeline.retry_delay_ms == 100
    
    def test_successful_invocation(self, pipeline, mock_lambda_client):
        """Test successful Lambda invocation."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        
        # Act
        result = pipeline.process(
            text='Hello everyone',
            session_id='test-session-123',
            source_language='en'
        )
        
        # Assert
        assert result is True
        mock_lambda_client.invoke.assert_called_once()
        
        # Verify invocation parameters
        call_args = mock_lambda_client.invoke.call_args
        assert call_args[1]['FunctionName'] == 'TestTranslationFunction'
        assert call_args[1]['InvocationType'] == 'Event'
        
        # Verify payload structure
        payload = json.loads(call_args[1]['Payload'])
        assert payload['sessionId'] == 'test-session-123'
        assert payload['sourceLanguage'] == 'en'
        assert payload['transcriptText'] == 'Hello everyone'
        assert payload['isPartial'] is False
        assert payload['stabilityScore'] == 1.0
        assert 'timestamp' in payload
        assert 'emotionDynamics' in payload
    
    def test_successful_invocation_with_202_status(self, pipeline, mock_lambda_client):
        """Test successful invocation with 202 status code."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 202}
        
        # Act
        result = pipeline.process(
            text='Test text',
            session_id='test-123',
            source_language='en'
        )
        
        # Assert
        assert result is True
    
    def test_payload_with_all_fields(self, pipeline, mock_lambda_client):
        """Test payload construction with all required fields."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        emotion_data = {
            'volume': 0.7,
            'rate': 1.2,
            'energy': 0.8
        }
        
        # Act
        result = pipeline.process(
            text='Hello world',
            session_id='session-456',
            source_language='es',
            is_partial=True,
            stability_score=0.85,
            timestamp=1699500000000,
            emotion_dynamics=emotion_data
        )
        
        # Assert
        assert result is True
        
        # Verify payload
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        
        assert payload['sessionId'] == 'session-456'
        assert payload['sourceLanguage'] == 'es'
        assert payload['transcriptText'] == 'Hello world'
        assert payload['isPartial'] is True
        assert payload['stabilityScore'] == 0.85
        assert payload['timestamp'] == 1699500000000
        assert payload['emotionDynamics'] == emotion_data
    
    def test_default_emotion_values(self, pipeline, mock_lambda_client):
        """Test default emotion values when not provided."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        
        # Act
        result = pipeline.process(
            text='Test',
            session_id='test-123',
            source_language='en'
        )
        
        # Assert
        assert result is True
        
        # Verify default emotion values
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        
        emotion = payload['emotionDynamics']
        assert emotion['volume'] == 0.5
        assert emotion['rate'] == 1.0
        assert emotion['energy'] == 0.5
    
    def test_asynchronous_invocation(self, pipeline, mock_lambda_client):
        """Test that invocation uses Event type (asynchronous)."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        
        # Act
        pipeline.process(
            text='Test',
            session_id='test-123',
            source_language='en'
        )
        
        # Assert
        call_args = mock_lambda_client.invoke.call_args
        assert call_args[1]['InvocationType'] == 'Event'
    
    def test_retry_on_client_error(self, pipeline, mock_lambda_client):
        """Test retry logic with transient ClientError."""
        # Arrange
        error_response = {
            'Error': {
                'Code': 'ServiceException',
                'Message': 'Service temporarily unavailable'
            }
        }
        
        # First two calls fail, third succeeds
        mock_lambda_client.invoke.side_effect = [
            ClientError(error_response, 'Invoke'),
            ClientError(error_response, 'Invoke'),
            {'StatusCode': 200}
        ]
        
        # Act
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = pipeline.process(
                text='Test',
                session_id='test-123',
                source_language='en'
            )
        
        # Assert
        assert result is True
        assert mock_lambda_client.invoke.call_count == 3
    
    def test_failure_after_max_retries(self, pipeline, mock_lambda_client):
        """Test failure after max retries exceeded."""
        # Arrange
        error_response = {
            'Error': {
                'Code': 'ServiceException',
                'Message': 'Service unavailable'
            }
        }
        
        # All calls fail
        mock_lambda_client.invoke.side_effect = ClientError(
            error_response,
            'Invoke'
        )
        
        # Act
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = pipeline.process(
                text='Test',
                session_id='test-123',
                source_language='en'
            )
        
        # Assert
        assert result is False
        # Should try 3 times (initial + 2 retries)
        assert mock_lambda_client.invoke.call_count == 3
    
    def test_unexpected_error_handling(self, pipeline, mock_lambda_client):
        """Test handling of unexpected exceptions."""
        # Arrange
        mock_lambda_client.invoke.side_effect = Exception('Unexpected error')
        
        # Act
        with patch('time.sleep'):
            result = pipeline.process(
                text='Test',
                session_id='test-123',
                source_language='en'
            )
        
        # Assert
        assert result is False
        assert mock_lambda_client.invoke.call_count == 3
    
    def test_unexpected_status_code_retries(self, pipeline, mock_lambda_client):
        """Test retry on unexpected status code."""
        # Arrange
        # First two calls return unexpected status, third succeeds
        mock_lambda_client.invoke.side_effect = [
            {'StatusCode': 500},
            {'StatusCode': 503},
            {'StatusCode': 200}
        ]
        
        # Act
        with patch('time.sleep'):
            result = pipeline.process(
                text='Test',
                session_id='test-123',
                source_language='en'
            )
        
        # Assert
        assert result is True
        assert mock_lambda_client.invoke.call_count == 3
    
    def test_partial_result_flag(self, pipeline, mock_lambda_client):
        """Test partial result flag in payload."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        
        # Act - partial result
        pipeline.process(
            text='Partial text',
            session_id='test-123',
            source_language='en',
            is_partial=True
        )
        
        # Assert
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        assert payload['isPartial'] is True
        
        # Act - final result
        pipeline.process(
            text='Final text',
            session_id='test-123',
            source_language='en',
            is_partial=False
        )
        
        # Assert
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        assert payload['isPartial'] is False
    
    def test_stability_score_in_payload(self, pipeline, mock_lambda_client):
        """Test stability score included in payload."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        
        # Act
        pipeline.process(
            text='Test',
            session_id='test-123',
            source_language='en',
            stability_score=0.92
        )
        
        # Assert
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        assert payload['stabilityScore'] == 0.92
    
    def test_custom_timestamp(self, pipeline, mock_lambda_client):
        """Test custom timestamp in payload."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        custom_timestamp = 1699500000000
        
        # Act
        pipeline.process(
            text='Test',
            session_id='test-123',
            source_language='en',
            timestamp=custom_timestamp
        )
        
        # Assert
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        assert payload['timestamp'] == custom_timestamp
    
    def test_auto_generated_timestamp(self, pipeline, mock_lambda_client):
        """Test auto-generated timestamp when not provided."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        
        # Act
        with patch('time.time', return_value=1699500000.0):
            pipeline.process(
                text='Test',
                session_id='test-123',
                source_language='en'
            )
        
        # Assert
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        assert payload['timestamp'] == 1699500000000
    
    def test_get_default_emotion(self, pipeline):
        """Test _get_default_emotion method."""
        # Act
        emotion = pipeline._get_default_emotion()
        
        # Assert
        assert emotion['volume'] == 0.5
        assert emotion['rate'] == 1.0
        assert emotion['energy'] == 0.5
    
    def test_multiple_invocations(self, pipeline, mock_lambda_client):
        """Test multiple successful invocations."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        
        # Act
        result1 = pipeline.process('Text 1', 'session-1', 'en')
        result2 = pipeline.process('Text 2', 'session-2', 'es')
        result3 = pipeline.process('Text 3', 'session-3', 'fr')
        
        # Assert
        assert result1 is True
        assert result2 is True
        assert result3 is True
        assert mock_lambda_client.invoke.call_count == 3
    
    def test_empty_text_handling(self, pipeline, mock_lambda_client):
        """Test handling of empty text."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        
        # Act
        result = pipeline.process(
            text='',
            session_id='test-123',
            source_language='en'
        )
        
        # Assert
        assert result is True
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        assert payload['transcriptText'] == ''
    
    def test_long_text_handling(self, pipeline, mock_lambda_client):
        """Test handling of long text."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        long_text = 'A' * 10000
        
        # Act
        result = pipeline.process(
            text=long_text,
            session_id='test-123',
            source_language='en'
        )
        
        # Assert
        assert result is True
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        assert payload['transcriptText'] == long_text
    
    def test_special_characters_in_text(self, pipeline, mock_lambda_client):
        """Test handling of special characters in text."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        special_text = 'Hello! How are you? I\'m fine. "Great" & <awesome>'
        
        # Act
        result = pipeline.process(
            text=special_text,
            session_id='test-123',
            source_language='en'
        )
        
        # Assert
        assert result is True
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        assert payload['transcriptText'] == special_text
    
    def test_unicode_text_handling(self, pipeline, mock_lambda_client):
        """Test handling of Unicode text."""
        # Arrange
        mock_lambda_client.invoke.return_value = {'StatusCode': 200}
        unicode_text = 'Hello 世界 مرحبا мир'
        
        # Act
        result = pipeline.process(
            text=unicode_text,
            session_id='test-123',
            source_language='en'
        )
        
        # Assert
        assert result is True
        call_args = mock_lambda_client.invoke.call_args
        payload = json.loads(call_args[1]['Payload'])
        assert payload['transcriptText'] == unicode_text
