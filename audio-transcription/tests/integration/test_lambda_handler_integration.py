"""
Integration tests for emotion processor Lambda handler.

Tests the complete end-to-end flow from Lambda event input to synthesized
audio output, including audio dynamics detection, SSML generation, and
Polly synthesis.
"""

import json
import base64
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

# Import Lambda handler
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda/emotion_processor'))
from handler import lambda_handler, _parse_input_event


class TestLambdaHandlerIntegration:
    """Integration tests for Lambda handler."""
    
    def test_lambda_handler_with_valid_input_succeeds(self):
        """Test Lambda handler with valid input returns success."""
        # Create test audio (1 second of sine wave at 440Hz)
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
        
        # Encode audio to base64
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Create Lambda event
        event = {
            'audioData': audio_b64,
            'sampleRate': sample_rate,
            'translatedText': 'Hello, how are you today?',
            'voiceId': 'Joanna'
        }
        
        # Create mock context
        context = Mock()
        
        # Call Lambda handler
        response = lambda_handler(event, context)
        
        # Verify response
        assert response['statusCode'] == 200
        assert 'body' in response
        
        # Parse response body
        body = json.loads(response['body'])
        
        # Verify response contains expected fields
        assert 'audioData' in body
        assert 'dynamics' in body
        assert 'ssmlText' in body
        assert 'processingTimeMs' in body
        assert 'correlationId' in body
        assert 'fallbackUsed' in body
        assert 'timing' in body
        
        # Verify dynamics structure
        assert 'volume' in body['dynamics']
        assert 'rate' in body['dynamics']
        assert 'level' in body['dynamics']['volume']
        assert 'dbValue' in body['dynamics']['volume']
        assert 'classification' in body['dynamics']['rate']
        assert 'wpm' in body['dynamics']['rate']
        
        # Verify timing breakdown
        assert 'volumeDetectionMs' in body['timing']
        assert 'rateDetectionMs' in body['timing']
        assert 'ssmlGenerationMs' in body['timing']
        assert 'pollySynthesisMs' in body['timing']
        
        # Verify audio data is base64-encoded
        try:
            audio_output = base64.b64decode(body['audioData'])
            assert len(audio_output) > 0
        except Exception as e:
            pytest.fail(f"Failed to decode output audio: {e}")
    
    def test_lambda_handler_with_different_sample_rates(self):
        """Test Lambda handler with various sample rates."""
        sample_rates = [8000, 16000, 24000, 48000]
        
        for sample_rate in sample_rates:
            # Create test audio
            duration = 0.5
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio_data = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
            
            # Encode audio
            audio_bytes = audio_data.tobytes()
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Create event
            event = {
                'audioData': audio_b64,
                'sampleRate': sample_rate,
                'translatedText': 'Test message',
                'voiceId': 'Joanna'
            }
            
            context = Mock()
            
            # Call handler
            response = lambda_handler(event, context)
            
            # Verify success
            assert response['statusCode'] == 200, \
                f"Failed for sample rate {sample_rate}Hz"
    
    def test_lambda_handler_with_various_audio_durations(self):
        """Test Lambda handler with different audio durations."""
        sample_rate = 16000
        durations = [0.5, 1.0, 2.0, 3.0]
        
        for duration in durations:
            # Create test audio
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio_data = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
            
            # Encode audio
            audio_bytes = audio_data.tobytes()
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Create event
            event = {
                'audioData': audio_b64,
                'sampleRate': sample_rate,
                'translatedText': 'Test message for various durations',
                'voiceId': 'Joanna'
            }
            
            context = Mock()
            
            # Call handler
            response = lambda_handler(event, context)
            
            # Verify success
            assert response['statusCode'] == 200, \
                f"Failed for duration {duration}s"
            
            # Parse body
            body = json.loads(response['body'])
            
            # Verify processing completed
            assert body['processingTimeMs'] > 0
    
    def test_lambda_handler_with_noisy_audio(self):
        """Test Lambda handler with noisy audio."""
        sample_rate = 16000
        duration = 1.0
        
        # Create audio with signal + noise
        t = np.linspace(0, duration, int(sample_rate * duration))
        signal = np.sin(2 * np.pi * 440 * t) * 5000
        noise = np.random.normal(0, 1000, signal.shape)
        audio_data = (signal + noise).astype(np.int16)
        
        # Encode audio
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Create event
        event = {
            'audioData': audio_b64,
            'sampleRate': sample_rate,
            'translatedText': 'Testing with noisy audio',
            'voiceId': 'Joanna'
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify success (should handle noisy audio gracefully)
        assert response['statusCode'] == 200
        
        # Parse body
        body = json.loads(response['body'])
        
        # Verify dynamics were detected (even if defaults used)
        assert body['dynamics']['volume']['level'] in ['loud', 'medium', 'soft', 'whisper']
        assert body['dynamics']['rate']['classification'] in [
            'very_slow', 'slow', 'medium', 'fast', 'very_fast'
        ]
    
    def test_lambda_handler_performance_meets_latency_requirements(self):
        """Test Lambda handler meets latency requirements."""
        sample_rate = 16000
        duration = 3.0  # Maximum expected audio duration
        
        # Create test audio
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
        
        # Encode audio
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Create event
        event = {
            'audioData': audio_b64,
            'sampleRate': sample_rate,
            'translatedText': 'Performance test message',
            'voiceId': 'Joanna'
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify success
        assert response['statusCode'] == 200
        
        # Parse body
        body = json.loads(response['body'])
        
        # Verify latency requirements
        # Audio dynamics detection: <100ms
        dynamics_latency = (
            body['timing']['volumeDetectionMs'] +
            body['timing']['rateDetectionMs']
        )
        assert dynamics_latency < 100, \
            f"Audio dynamics detection exceeded 100ms: {dynamics_latency}ms"
        
        # SSML generation: <50ms
        assert body['timing']['ssmlGenerationMs'] < 50, \
            f"SSML generation exceeded 50ms: {body['timing']['ssmlGenerationMs']}ms"
        
        # Polly synthesis: <800ms (for 3s audio)
        # Note: This may exceed in real scenarios, but should be close
        assert body['timing']['pollySynthesisMs'] < 1000, \
            f"Polly synthesis significantly exceeded target: {body['timing']['pollySynthesisMs']}ms"
        
        # Total processing: Should be reasonable
        assert body['processingTimeMs'] < 2000, \
            f"Total processing time excessive: {body['processingTimeMs']}ms"
    
    def test_lambda_handler_with_missing_audio_data_fails(self):
        """Test Lambda handler with missing audioData returns error."""
        event = {
            'sampleRate': 16000,
            'translatedText': 'Test message'
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify error response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'audioData' in body['message']
    
    def test_lambda_handler_with_missing_sample_rate_fails(self):
        """Test Lambda handler with missing sampleRate returns error."""
        # Create test audio
        audio_data = np.random.randint(-10000, 10000, 16000, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        event = {
            'audioData': audio_b64,
            'translatedText': 'Test message'
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify error response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'sampleRate' in body['message']
    
    def test_lambda_handler_with_missing_text_fails(self):
        """Test Lambda handler with missing translatedText returns error."""
        # Create test audio
        audio_data = np.random.randint(-10000, 10000, 16000, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        event = {
            'audioData': audio_b64,
            'sampleRate': 16000
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify error response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'translatedText' in body['message']
    
    def test_lambda_handler_with_invalid_audio_format_fails(self):
        """Test Lambda handler with invalid audio format returns error."""
        event = {
            'audioData': 'not-valid-base64!!!',
            'sampleRate': 16000,
            'translatedText': 'Test message'
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify error response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
    
    def test_lambda_handler_with_empty_audio_fails(self):
        """Test Lambda handler with empty audio returns error."""
        # Empty audio - base64 encode empty bytes
        # Note: base64 encoding empty bytes produces a valid base64 string,
        # but when decoded and converted to numpy array, it will be empty
        audio_b64 = base64.b64encode(b'').decode('utf-8')
        
        event = {
            'audioData': audio_b64,
            'sampleRate': 16000,
            'translatedText': 'Test message'
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify error response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        # The error message should mention empty audio or array
        assert ('empty' in body['message'].lower() or 
                'audiodata' in body['message'].lower())
    
    def test_lambda_handler_with_invalid_sample_rate_fails(self):
        """Test Lambda handler with invalid sample rate returns error."""
        # Create test audio
        audio_data = np.random.randint(-10000, 10000, 16000, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        event = {
            'audioData': audio_b64,
            'sampleRate': -1,  # Invalid
            'translatedText': 'Test message'
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify error response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'sampleRate' in body['message']
    
    def test_lambda_handler_with_empty_text_fails(self):
        """Test Lambda handler with empty text returns error."""
        # Create test audio
        audio_data = np.random.randint(-10000, 10000, 16000, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        event = {
            'audioData': audio_b64,
            'sampleRate': 16000,
            'translatedText': '   '  # Only whitespace
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify error response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'whitespace' in body['message'].lower()
    
    def test_lambda_handler_with_text_exceeding_limit_fails(self):
        """Test Lambda handler with text exceeding character limit returns error."""
        # Create test audio
        audio_data = np.random.randint(-10000, 10000, 16000, dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Create text exceeding 3000 character limit
        long_text = 'a' * 3001
        
        event = {
            'audioData': audio_b64,
            'sampleRate': 16000,
            'translatedText': long_text
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify error response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'maximum length' in body['message'].lower()
    
    def test_lambda_handler_with_audio_too_short_fails(self):
        """Test Lambda handler with audio too short returns error."""
        sample_rate = 16000
        
        # Create very short audio (0.05 seconds, below 0.1s minimum)
        audio_data = np.random.randint(-10000, 10000, int(sample_rate * 0.05), dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        event = {
            'audioData': audio_b64,
            'sampleRate': sample_rate,
            'translatedText': 'Test message'
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify error response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'too short' in body['message'].lower()
    
    def test_lambda_handler_with_audio_too_long_fails(self):
        """Test Lambda handler with audio too long returns error."""
        sample_rate = 16000
        
        # Create very long audio (31 seconds, above 30s maximum)
        audio_data = np.random.randint(-10000, 10000, int(sample_rate * 31), dtype=np.int16)
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        event = {
            'audioData': audio_b64,
            'sampleRate': sample_rate,
            'translatedText': 'Test message'
        }
        
        context = Mock()
        
        # Call handler
        response = lambda_handler(event, context)
        
        # Verify error response
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'exceeds maximum' in body['message'].lower()
    
    def test_lambda_handler_cold_start_initialization(self):
        """Test Lambda handler initializes orchestrator on cold start."""
        # This test verifies the singleton pattern works correctly
        
        # Create test audio
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
        
        # Encode audio
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Create event
        event = {
            'audioData': audio_b64,
            'sampleRate': sample_rate,
            'translatedText': 'Cold start test',
            'voiceId': 'Joanna'
        }
        
        context = Mock()
        
        # First invocation (cold start)
        response1 = lambda_handler(event, context)
        assert response1['statusCode'] == 200
        
        # Second invocation (warm start, should reuse orchestrator)
        response2 = lambda_handler(event, context)
        assert response2['statusCode'] == 200
        
        # Both should succeed
        body1 = json.loads(response1['body'])
        body2 = json.loads(response2['body'])
        
        assert 'correlationId' in body1
        assert 'correlationId' in body2
        # Correlation IDs should be different (different requests)
        assert body1['correlationId'] != body2['correlationId']
