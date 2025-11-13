"""
Unit tests for error scenarios in emotion dynamics detection.

Tests error handling, fallback mechanisms, and graceful degradation
across all components: VolumeDetector, SpeakingRateDetector, SSMLGenerator,
PollyClient, and AudioDynamicsOrchestrator.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
from io import BytesIO

from emotion_dynamics.detectors.volume_detector import VolumeDetector
from emotion_dynamics.detectors.speaking_rate_detector import SpeakingRateDetector
from emotion_dynamics.generators.ssml_generator import SSMLGenerator
from emotion_dynamics.clients.polly_client import PollyClient
from emotion_dynamics.orchestrator import AudioDynamicsOrchestrator
from emotion_dynamics.models.audio_dynamics import AudioDynamics
from emotion_dynamics.models.volume_result import VolumeResult
from emotion_dynamics.models.rate_result import RateResult
from emotion_dynamics.models.processing_options import ProcessingOptions
from emotion_dynamics.exceptions import (
    VolumeDetectionError,
    RateDetectionError,
    SSMLValidationError,
    SynthesisError,
    EmotionDynamicsError
)


class TestLibrosaProcessingFailures:
    """Test librosa processing failures and fallback behavior."""
    
    @pytest.fixture
    def sample_audio(self):
        """Create sample audio data."""
        return np.random.randn(16000).astype(np.float32)
    
    def test_volume_detector_librosa_rms_failure(self, sample_audio):
        """Test volume detector handles librosa RMS calculation failure."""
        detector = VolumeDetector()
        
        # Mock librosa.feature.rms to raise exception
        with patch.object(detector.librosa.feature, 'rms', side_effect=Exception("RMS calculation failed")):
            result = detector.detect_volume(sample_audio, 16000)
            
            # Should fall back to default medium volume
            assert result.level == 'medium'
            assert result.db_value == -15.0
    
    def test_rate_detector_librosa_onset_failure(self, sample_audio):
        """Test rate detector handles librosa onset detection failure."""
        detector = SpeakingRateDetector()
        
        # Mock librosa.onset.onset_detect to raise exception
        with patch.object(detector.librosa.onset, 'onset_detect', side_effect=Exception("Onset detection failed")):
            result = detector.detect_rate(sample_audio, 16000)
            
            # Should fall back to default medium rate
            assert result.classification == 'medium'
            assert result.wpm == 145.0
            assert result.onset_count == 0
    
    def test_volume_detector_with_corrupted_audio_data(self):
        """Test volume detector handles corrupted audio data."""
        detector = VolumeDetector()
        
        # Test with NaN values - librosa may process these as very low volume
        corrupted_audio = np.array([np.nan, np.nan, np.nan])
        result = detector.detect_volume(corrupted_audio, 16000)
        
        # Should return a valid result (may be whisper due to NaN processing)
        assert result.level in ['whisper', 'soft', 'medium']
        assert not np.isnan(result.db_value)
        assert not np.isinf(result.db_value)
    
    def test_rate_detector_with_corrupted_audio_data(self):
        """Test rate detector handles corrupted audio data."""
        detector = SpeakingRateDetector()
        
        # Test with infinite values
        corrupted_audio = np.array([np.inf, -np.inf, np.inf])
        result = detector.detect_rate(corrupted_audio, 16000)
        
        # Should fall back to default
        assert result.classification == 'medium'
        assert result.wpm == 145.0


class TestInvalidAudioDataHandling:
    """Test handling of invalid audio data across components."""
    
    def test_volume_detector_with_empty_array(self):
        """Test volume detector with empty audio array."""
        detector = VolumeDetector()
        result = detector.detect_volume(np.array([]), 16000)
        
        assert result.level == 'medium'
        assert result.db_value == -15.0
    
    def test_rate_detector_with_empty_array(self):
        """Test rate detector with empty audio array."""
        detector = SpeakingRateDetector()
        result = detector.detect_rate(np.array([]), 16000)
        
        assert result.classification == 'medium'
        assert result.wpm == 145.0
    
    def test_volume_detector_with_non_numpy_array(self):
        """Test volume detector with non-numpy array input."""
        detector = VolumeDetector()
        result = detector.detect_volume([1, 2, 3, 4, 5], 16000)
        
        assert result.level == 'medium'
        assert result.db_value == -15.0
    
    def test_rate_detector_with_non_numpy_array(self):
        """Test rate detector with non-numpy array input."""
        detector = SpeakingRateDetector()
        result = detector.detect_rate([1, 2, 3, 4, 5], 16000)
        
        assert result.classification == 'medium'
        assert result.wpm == 145.0
    
    def test_volume_detector_with_invalid_sample_rate(self):
        """Test volume detector with invalid sample rate."""
        detector = VolumeDetector()
        audio = np.random.randn(16000).astype(np.float32)
        
        # Test with negative sample rate
        result = detector.detect_volume(audio, -16000)
        assert result.level == 'medium'
        
        # Test with zero sample rate
        result = detector.detect_volume(audio, 0)
        assert result.level == 'medium'
    
    def test_rate_detector_with_invalid_sample_rate(self):
        """Test rate detector with invalid sample rate."""
        detector = SpeakingRateDetector()
        audio = np.random.randn(16000).astype(np.float32)
        
        # Test with negative sample rate
        result = detector.detect_rate(audio, -16000)
        assert result.classification == 'medium'
        
        # Test with zero sample rate
        result = detector.detect_rate(audio, 0)
        assert result.classification == 'medium'


class TestSSMLValidationErrors:
    """Test SSML validation error handling."""
    
    @pytest.fixture
    def generator(self):
        """Create SSML generator instance."""
        return SSMLGenerator()
    
    @pytest.fixture
    def sample_dynamics(self):
        """Create sample dynamics."""
        volume = VolumeResult(level='medium', db_value=-15.0, timestamp=None)
        rate = RateResult(classification='medium', wpm=145.0, onset_count=50, timestamp=None)
        return AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
    
    def test_ssml_generation_with_invalid_dynamics_attributes(self, generator):
        """Test SSML generation with invalid dynamics attributes."""
        volume = VolumeResult(level='medium', db_value=-15.0, timestamp=None)
        rate = RateResult(classification='medium', wpm=145.0, onset_count=50, timestamp=None)
        dynamics = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
        
        # Mock to_ssml_attributes to return invalid values
        with patch.object(dynamics, 'to_ssml_attributes', return_value={'volume': 'invalid', 'rate': 'medium'}):
            with pytest.raises(SSMLValidationError):
                generator.generate_ssml("Test text", dynamics)
    
    def test_ssml_generation_with_exception_falls_back_to_plain_text(self, generator, sample_dynamics):
        """Test SSML generation falls back to plain text on exception."""
        # Mock to_ssml_attributes to raise exception
        with patch.object(sample_dynamics, 'to_ssml_attributes', side_effect=Exception("Unexpected error")):
            ssml = generator.generate_ssml("Test text", sample_dynamics)
            
            # Should fall back to plain SSML
            assert '<speak>' in ssml
            assert '<prosody' not in ssml
            assert 'Test text' in ssml
    
    def test_ssml_generation_with_empty_text(self, generator, sample_dynamics):
        """Test SSML generation with empty text."""
        ssml = generator.generate_ssml("", sample_dynamics)
        assert ssml == ""
    
    def test_ssml_generation_with_none_text(self, generator, sample_dynamics):
        """Test SSML generation with None text."""
        ssml = generator.generate_ssml(None, sample_dynamics)
        assert ssml == ""


class TestPollySSMLRejection:
    """Test Polly SSML rejection and fallback."""
    
    @pytest.fixture
    def mock_polly_client(self):
        """Create mocked Polly client."""
        with patch('emotion_dynamics.clients.polly_client.boto3.client') as mock_client:
            mock_polly = Mock()
            mock_client.return_value = mock_polly
            yield mock_polly
    
    def test_polly_invalid_ssml_exception_fallback(self, mock_polly_client):
        """Test Polly falls back to plain text on InvalidSsmlException."""
        client = PollyClient()
        
        ssml_text = '<speak><prosody rate="medium" volume="medium">Test</prosody></speak>'
        
        # First call fails with InvalidSsmlException, second succeeds
        error_response = {'Error': {'Code': 'InvalidSsmlException', 'Message': 'Invalid SSML'}}
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'fallback_audio')}
        ]
        
        audio = client.synthesize_speech(text=ssml_text, text_type='ssml')
        
        assert audio == b'fallback_audio'
        assert mock_polly_client.synthesize_speech.call_count == 2
    
    def test_polly_ssml_marks_not_supported_fallback(self, mock_polly_client):
        """Test Polly falls back on SsmlMarksNotSupportedForInputTypeException."""
        client = PollyClient()
        
        ssml_text = '<speak><prosody rate="medium" volume="medium">Test</prosody></speak>'
        
        error_response = {
            'Error': {
                'Code': 'SsmlMarksNotSupportedForInputTypeException',
                'Message': 'SSML marks not supported'
            }
        }
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'fallback_audio')}
        ]
        
        audio = client.synthesize_speech(text=ssml_text, text_type='ssml')
        
        assert audio == b'fallback_audio'
        assert mock_polly_client.synthesize_speech.call_count == 2


class TestPollyThrottlingAndRecovery:
    """Test Polly throttling and retry logic."""
    
    @pytest.fixture
    def mock_polly_client(self):
        """Create mocked Polly client."""
        with patch('emotion_dynamics.clients.polly_client.boto3.client') as mock_client:
            mock_polly = Mock()
            mock_client.return_value = mock_polly
            yield mock_polly
    
    def test_polly_throttling_exception_retry_success(self, mock_polly_client):
        """Test Polly retries on ThrottlingException and succeeds."""
        client = PollyClient()
        
        error_response = {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}}
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'success_audio')}
        ]
        
        with patch('emotion_dynamics.clients.polly_client.time.sleep'):
            audio = client.synthesize_speech(text='Test', text_type='text')
        
        assert audio == b'success_audio'
        assert mock_polly_client.synthesize_speech.call_count == 3
    
    def test_polly_throttling_exception_retry_exhaustion(self, mock_polly_client):
        """Test Polly raises SynthesisError after exhausting retries."""
        client = PollyClient()
        
        error_response = {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}}
        mock_polly_client.synthesize_speech.side_effect = ClientError(error_response, 'SynthesizeSpeech')
        
        with patch('emotion_dynamics.clients.polly_client.time.sleep'):
            with pytest.raises(SynthesisError) as exc_info:
                client.synthesize_speech(text='Test', text_type='text')
        
        assert 'after 3 retries' in str(exc_info.value)
        assert mock_polly_client.synthesize_speech.call_count == 4  # Initial + 3 retries
    
    def test_polly_service_failure_exception_retry(self, mock_polly_client):
        """Test Polly retries on ServiceFailureException."""
        client = PollyClient()
        
        error_response = {'Error': {'Code': 'ServiceFailureException', 'Message': 'Service failure'}}
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'success_audio')}
        ]
        
        with patch('emotion_dynamics.clients.polly_client.time.sleep'):
            audio = client.synthesize_speech(text='Test', text_type='text')
        
        assert audio == b'success_audio'
        assert mock_polly_client.synthesize_speech.call_count == 2
    
    def test_polly_service_unavailable_exception_retry(self, mock_polly_client):
        """Test Polly retries on ServiceUnavailableException."""
        client = PollyClient()
        
        error_response = {'Error': {'Code': 'ServiceUnavailableException', 'Message': 'Service unavailable'}}
        mock_polly_client.synthesize_speech.side_effect = [
            ClientError(error_response, 'SynthesizeSpeech'),
            {'AudioStream': BytesIO(b'success_audio')}
        ]
        
        with patch('emotion_dynamics.clients.polly_client.time.sleep'):
            audio = client.synthesize_speech(text='Test', text_type='text')
        
        assert audio == b'success_audio'
        assert mock_polly_client.synthesize_speech.call_count == 2


class TestConcurrentErrorHandling:
    """Test concurrent error handling in orchestrator."""
    
    @pytest.fixture
    def sample_audio(self):
        """Create sample audio data."""
        return np.random.randn(16000).astype(np.float32)
    
    def test_orchestrator_handles_volume_detector_failure(self, sample_audio):
        """Test orchestrator handles volume detector failure gracefully."""
        volume_detector = VolumeDetector()
        rate_detector = SpeakingRateDetector()
        ssml_generator = SSMLGenerator()
        polly_client = Mock(spec=PollyClient)
        polly_client.synthesize_speech.return_value = b'audio_data'
        
        orchestrator = AudioDynamicsOrchestrator(
            volume_detector=volume_detector,
            rate_detector=rate_detector,
            ssml_generator=ssml_generator,
            polly_client=polly_client
        )
        
        # Mock volume detector to fail
        with patch.object(volume_detector, 'detect_volume', side_effect=Exception("Volume detection failed")):
            dynamics, volume_ms, rate_ms, combined_ms = orchestrator.detect_audio_dynamics(
                audio_data=sample_audio,
                sample_rate=16000
            )
            
            # Should use default volume
            assert dynamics.volume.level == 'medium'
            assert dynamics.volume.db_value == -15.0
            # Rate should still be detected
            assert dynamics.rate.classification in ['very_slow', 'slow', 'medium', 'fast', 'very_fast']
    
    def test_orchestrator_handles_rate_detector_failure(self, sample_audio):
        """Test orchestrator handles rate detector failure gracefully."""
        volume_detector = VolumeDetector()
        rate_detector = SpeakingRateDetector()
        ssml_generator = SSMLGenerator()
        polly_client = Mock(spec=PollyClient)
        polly_client.synthesize_speech.return_value = b'audio_data'
        
        orchestrator = AudioDynamicsOrchestrator(
            volume_detector=volume_detector,
            rate_detector=rate_detector,
            ssml_generator=ssml_generator,
            polly_client=polly_client
        )
        
        # Mock rate detector to fail
        with patch.object(rate_detector, 'detect_rate', side_effect=Exception("Rate detection failed")):
            dynamics, volume_ms, rate_ms, combined_ms = orchestrator.detect_audio_dynamics(
                audio_data=sample_audio,
                sample_rate=16000
            )
            
            # Volume should still be detected
            assert dynamics.volume.level in ['loud', 'medium', 'soft', 'whisper']
            # Should use default rate
            assert dynamics.rate.classification == 'medium'
            assert dynamics.rate.wpm == 145.0
    
    def test_orchestrator_handles_both_detectors_failure(self, sample_audio):
        """Test orchestrator handles both detectors failing."""
        volume_detector = VolumeDetector()
        rate_detector = SpeakingRateDetector()
        ssml_generator = SSMLGenerator()
        polly_client = Mock(spec=PollyClient)
        polly_client.synthesize_speech.return_value = b'audio_data'
        
        orchestrator = AudioDynamicsOrchestrator(
            volume_detector=volume_detector,
            rate_detector=rate_detector,
            ssml_generator=ssml_generator,
            polly_client=polly_client
        )
        
        # Mock both detectors to fail
        with patch.object(volume_detector, 'detect_volume', side_effect=Exception("Volume failed")):
            with patch.object(rate_detector, 'detect_rate', side_effect=Exception("Rate failed")):
                dynamics, volume_ms, rate_ms, combined_ms = orchestrator.detect_audio_dynamics(
                    audio_data=sample_audio,
                    sample_rate=16000
                )
                
                # Should use defaults for both
                assert dynamics.volume.level == 'medium'
                assert dynamics.volume.db_value == -15.0
                assert dynamics.rate.classification == 'medium'
                assert dynamics.rate.wpm == 145.0
    
    def test_orchestrator_end_to_end_with_ssml_failure(self, sample_audio):
        """Test orchestrator handles SSML generation failure."""
        volume_detector = VolumeDetector()
        rate_detector = SpeakingRateDetector()
        ssml_generator = SSMLGenerator()
        polly_client = Mock(spec=PollyClient)
        polly_client.synthesize_speech.return_value = b'audio_data'
        
        orchestrator = AudioDynamicsOrchestrator(
            volume_detector=volume_detector,
            rate_detector=rate_detector,
            ssml_generator=ssml_generator,
            polly_client=polly_client
        )
        
        # Mock SSML generator to fail on first call with dynamics
        original_generate = ssml_generator.generate_ssml
        call_count = [0]
        
        def failing_generate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1 and kwargs.get('dynamics') is not None:
                raise Exception("SSML generation failed")
            return original_generate(*args, **kwargs)
        
        ssml_generator.generate_ssml = failing_generate
        
        result = orchestrator.process_audio_and_text(
            audio_data=sample_audio,
            sample_rate=16000,
            translated_text='Test message'
        )
        
        # Should fall back to plain text
        assert result.fallback_used is True
        assert result.audio_stream == b'audio_data'
        assert '<speak>' in result.ssml_text
    
    def test_orchestrator_end_to_end_with_polly_failure_raises_error(self, sample_audio):
        """Test orchestrator raises error when Polly synthesis fails."""
        volume_detector = VolumeDetector()
        rate_detector = SpeakingRateDetector()
        ssml_generator = SSMLGenerator()
        polly_client = Mock(spec=PollyClient)
        polly_client.synthesize_speech.side_effect = Exception("Polly service unavailable")
        
        orchestrator = AudioDynamicsOrchestrator(
            volume_detector=volume_detector,
            rate_detector=rate_detector,
            ssml_generator=ssml_generator,
            polly_client=polly_client
        )
        
        with pytest.raises(EmotionDynamicsError) as exc_info:
            orchestrator.process_audio_and_text(
                audio_data=sample_audio,
                sample_rate=16000,
                translated_text='Test message'
            )
        
        assert "Speech synthesis failed" in str(exc_info.value)
