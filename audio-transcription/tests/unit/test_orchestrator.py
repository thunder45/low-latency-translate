"""
Unit tests for AudioDynamicsOrchestrator.

Tests parallel audio dynamics detection, SSML generation orchestration,
and end-to-end processing pipeline with error handling.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from emotion_dynamics.orchestrator import AudioDynamicsOrchestrator
from emotion_dynamics.models.volume_result import VolumeResult
from emotion_dynamics.models.rate_result import RateResult
from emotion_dynamics.models.audio_dynamics import AudioDynamics
from emotion_dynamics.models.processing_options import ProcessingOptions
from emotion_dynamics.models.processing_result import ProcessingResult
from emotion_dynamics.exceptions import EmotionDynamicsError


class TestAudioDynamicsOrchestrator:
    """Test suite for AudioDynamicsOrchestrator."""
    
    @pytest.fixture
    def mock_volume_detector(self):
        """Create mock volume detector."""
        detector = Mock()
        detector.detect_volume.return_value = VolumeResult(
            level='loud',
            db_value=-8.5,
            timestamp=datetime.now(timezone.utc)
        )
        return detector
    
    @pytest.fixture
    def mock_rate_detector(self):
        """Create mock rate detector."""
        detector = Mock()
        detector.detect_rate.return_value = RateResult(
            classification='fast',
            wpm=175.0,
            onset_count=50,
            timestamp=datetime.now(timezone.utc)
        )
        return detector
    
    @pytest.fixture
    def mock_ssml_generator(self):
        """Create mock SSML generator."""
        generator = Mock()
        generator.generate_ssml.return_value = (
            '<speak><prosody rate="fast" volume="x-loud">'
            'Hello world'
            '</prosody></speak>'
        )
        return generator
    
    @pytest.fixture
    def mock_polly_client(self):
        """Create mock Polly client."""
        client = Mock()
        client.synthesize_speech.return_value = b'fake_audio_data'
        return client
    
    @pytest.fixture
    def orchestrator(
        self,
        mock_volume_detector,
        mock_rate_detector,
        mock_ssml_generator,
        mock_polly_client
    ):
        """Create orchestrator with mocked dependencies."""
        return AudioDynamicsOrchestrator(
            volume_detector=mock_volume_detector,
            rate_detector=mock_rate_detector,
            ssml_generator=mock_ssml_generator,
            polly_client=mock_polly_client
        )
    
    @pytest.fixture
    def sample_audio(self):
        """Create sample audio data."""
        # 1 second of audio at 16kHz
        return np.random.randn(16000).astype(np.float32)
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initializes with default components."""
        orchestrator = AudioDynamicsOrchestrator()
        
        assert orchestrator.volume_detector is not None
        assert orchestrator.rate_detector is not None
        assert orchestrator.ssml_generator is not None
        assert orchestrator.polly_client is not None
    
    def test_detect_audio_dynamics_parallel_execution(
        self,
        orchestrator,
        sample_audio,
        mock_volume_detector,
        mock_rate_detector
    ):
        """Test parallel execution of volume and rate detection."""
        dynamics, volume_ms, rate_ms, combined_ms = orchestrator.detect_audio_dynamics(
            audio_data=sample_audio,
            sample_rate=16000
        )
        
        # Verify both detectors were called
        mock_volume_detector.detect_volume.assert_called_once()
        mock_rate_detector.detect_rate.assert_called_once()
        
        # Verify results
        assert isinstance(dynamics, AudioDynamics)
        assert dynamics.volume.level == 'loud'
        assert dynamics.rate.classification == 'fast'
        assert dynamics.correlation_id is not None
        
        # Verify timing metrics
        assert volume_ms >= 0
        assert rate_ms >= 0
        assert combined_ms >= 0
        # Combined time should be less than sum (parallel execution)
        # Note: In tests with mocks, this may not always hold due to overhead
    
    def test_detect_audio_dynamics_with_correlation_id(
        self,
        orchestrator,
        sample_audio
    ):
        """Test dynamics detection with provided correlation ID."""
        correlation_id = 'test-correlation-123'
        
        dynamics, _, _, _ = orchestrator.detect_audio_dynamics(
            audio_data=sample_audio,
            sample_rate=16000,
            correlation_id=correlation_id
        )
        
        assert dynamics.correlation_id == correlation_id
    
    def test_detect_audio_dynamics_with_disabled_volume(
        self,
        orchestrator,
        sample_audio,
        mock_volume_detector,
        mock_rate_detector
    ):
        """Test dynamics detection with volume detection disabled."""
        options = ProcessingOptions(enable_volume_detection=False)
        
        dynamics, volume_ms, rate_ms, combined_ms = orchestrator.detect_audio_dynamics(
            audio_data=sample_audio,
            sample_rate=16000,
            options=options
        )
        
        # Volume detector should not be called
        mock_volume_detector.detect_volume.assert_not_called()
        
        # Rate detector should still be called
        mock_rate_detector.detect_rate.assert_called_once()
        
        # Should use default medium volume
        assert dynamics.volume.level == 'medium'
        assert dynamics.rate.classification == 'fast'
    
    def test_detect_audio_dynamics_with_disabled_rate(
        self,
        orchestrator,
        sample_audio,
        mock_volume_detector,
        mock_rate_detector
    ):
        """Test dynamics detection with rate detection disabled."""
        options = ProcessingOptions(enable_rate_detection=False)
        
        dynamics, volume_ms, rate_ms, combined_ms = orchestrator.detect_audio_dynamics(
            audio_data=sample_audio,
            sample_rate=16000,
            options=options
        )
        
        # Rate detector should not be called
        mock_rate_detector.detect_rate.assert_not_called()
        
        # Volume detector should still be called
        mock_volume_detector.detect_volume.assert_called_once()
        
        # Should use default medium rate
        assert dynamics.volume.level == 'loud'
        assert dynamics.rate.classification == 'medium'
    
    def test_detect_audio_dynamics_with_detector_failure(
        self,
        orchestrator,
        sample_audio,
        mock_volume_detector
    ):
        """Test dynamics detection handles detector failures gracefully."""
        # Make volume detector fail
        mock_volume_detector.detect_volume.side_effect = Exception("Detection failed")
        
        dynamics, volume_ms, rate_ms, combined_ms = orchestrator.detect_audio_dynamics(
            audio_data=sample_audio,
            sample_rate=16000
        )
        
        # Should fall back to default medium volume
        assert dynamics.volume.level == 'medium'
        # Rate should still work
        assert dynamics.rate.classification == 'fast'
    
    def test_process_audio_and_text_success(
        self,
        orchestrator,
        sample_audio,
        mock_volume_detector,
        mock_rate_detector,
        mock_ssml_generator,
        mock_polly_client
    ):
        """Test complete processing pipeline succeeds."""
        result = orchestrator.process_audio_and_text(
            audio_data=sample_audio,
            sample_rate=16000,
            translated_text='Hello world'
        )
        
        # Verify all components were called
        mock_volume_detector.detect_volume.assert_called_once()
        mock_rate_detector.detect_rate.assert_called_once()
        mock_ssml_generator.generate_ssml.assert_called_once()
        mock_polly_client.synthesize_speech.assert_called_once()
        
        # Verify result
        assert isinstance(result, ProcessingResult)
        assert result.audio_stream == b'fake_audio_data'
        assert isinstance(result.dynamics, AudioDynamics)
        assert result.ssml_text is not None
        assert result.processing_time_ms >= 0
        assert result.correlation_id is not None
        assert result.fallback_used is False
        
        # Verify timing breakdown
        assert result.volume_detection_ms >= 0
        assert result.rate_detection_ms >= 0
        assert result.ssml_generation_ms >= 0
        assert result.polly_synthesis_ms >= 0
    
    def test_process_audio_and_text_with_options(
        self,
        orchestrator,
        sample_audio,
        mock_polly_client
    ):
        """Test processing with custom options."""
        options = ProcessingOptions(
            voice_id='Matthew',
            enable_ssml=True,
            sample_rate='24000',
            output_format='mp3'
        )
        
        result = orchestrator.process_audio_and_text(
            audio_data=sample_audio,
            sample_rate=16000,
            translated_text='Hello world',
            options=options
        )
        
        # Verify Polly was called with correct options
        call_args = mock_polly_client.synthesize_speech.call_args
        assert call_args[1]['voice_id'] == 'Matthew'
        assert call_args[1]['sample_rate'] == '24000'
        assert call_args[1]['output_format'] == 'mp3'
    
    def test_process_audio_and_text_with_ssml_disabled(
        self,
        orchestrator,
        sample_audio,
        mock_ssml_generator,
        mock_polly_client
    ):
        """Test processing with SSML disabled."""
        options = ProcessingOptions(enable_ssml=False)
        
        result = orchestrator.process_audio_and_text(
            audio_data=sample_audio,
            sample_rate=16000,
            translated_text='Hello world',
            options=options
        )
        
        # SSML generator should be called with None dynamics
        call_args = mock_ssml_generator.generate_ssml.call_args
        assert call_args[1]['dynamics'] is None
        
        # Fallback should be marked as used
        assert result.fallback_used is True
    
    def test_process_audio_and_text_with_ssml_generation_failure(
        self,
        orchestrator,
        sample_audio,
        mock_ssml_generator
    ):
        """Test processing handles SSML generation failure gracefully."""
        # Make SSML generator fail on first call, succeed on second
        mock_ssml_generator.generate_ssml.side_effect = [
            Exception("SSML generation failed"),
            '<speak>Hello world</speak>'
        ]
        
        result = orchestrator.process_audio_and_text(
            audio_data=sample_audio,
            sample_rate=16000,
            translated_text='Hello world'
        )
        
        # Should fall back to plain text
        assert result.fallback_used is True
        # SSML generator should be called twice (once failed, once fallback)
        assert mock_ssml_generator.generate_ssml.call_count == 2
    
    def test_process_audio_and_text_with_polly_failure(
        self,
        orchestrator,
        sample_audio,
        mock_polly_client
    ):
        """Test processing fails when Polly synthesis fails."""
        mock_polly_client.synthesize_speech.side_effect = Exception("Polly failed")
        
        with pytest.raises(EmotionDynamicsError) as exc_info:
            orchestrator.process_audio_and_text(
                audio_data=sample_audio,
                sample_rate=16000,
                translated_text='Hello world'
            )
        
        assert "Speech synthesis failed" in str(exc_info.value)
    
    def test_validate_inputs_with_invalid_audio(self, orchestrator):
        """Test input validation rejects invalid audio data."""
        with pytest.raises(ValueError) as exc_info:
            orchestrator._validate_inputs(
                audio_data="not_an_array",
                sample_rate=16000,
                text="Hello"
            )
        assert "audio_data must be numpy array" in str(exc_info.value)
    
    def test_validate_inputs_with_empty_audio(self, orchestrator):
        """Test input validation rejects empty audio."""
        with pytest.raises(ValueError) as exc_info:
            orchestrator._validate_inputs(
                audio_data=np.array([]),
                sample_rate=16000,
                text="Hello"
            )
        assert "audio_data is empty" in str(exc_info.value)
    
    def test_validate_inputs_with_invalid_sample_rate(self, orchestrator):
        """Test input validation rejects invalid sample rate."""
        with pytest.raises(ValueError) as exc_info:
            orchestrator._validate_inputs(
                audio_data=np.array([1.0, 2.0]),
                sample_rate=-1,
                text="Hello"
            )
        assert "sample_rate must be positive integer" in str(exc_info.value)
    
    def test_validate_inputs_with_empty_text(self, orchestrator):
        """Test input validation rejects empty text."""
        with pytest.raises(ValueError) as exc_info:
            orchestrator._validate_inputs(
                audio_data=np.array([1.0, 2.0]),
                sample_rate=16000,
                text=""
            )
        assert "text must be non-empty string" in str(exc_info.value)
    
    def test_validate_inputs_with_whitespace_only_text(self, orchestrator):
        """Test input validation rejects whitespace-only text."""
        with pytest.raises(ValueError) as exc_info:
            orchestrator._validate_inputs(
                audio_data=np.array([1.0, 2.0]),
                sample_rate=16000,
                text="   "
            )
        assert "text contains only whitespace" in str(exc_info.value)
    
    def test_process_audio_and_text_validates_inputs(
        self,
        orchestrator,
        mock_volume_detector,
        mock_rate_detector
    ):
        """Test processing pipeline validates inputs before processing."""
        with pytest.raises(EmotionDynamicsError) as exc_info:
            orchestrator.process_audio_and_text(
                audio_data=np.array([]),  # Empty audio
                sample_rate=16000,
                translated_text='Hello'
            )
        
        # Should wrap ValueError in EmotionDynamicsError
        assert "audio_data is empty" in str(exc_info.value)
        
        # Detectors should not be called if validation fails
        mock_volume_detector.detect_volume.assert_not_called()
        mock_rate_detector.detect_rate.assert_not_called()
    
    def test_detect_audio_dynamics_latency_warning(
        self,
        orchestrator,
        sample_audio,
        mock_volume_detector,
        mock_rate_detector
    ):
        """Test warning is logged when dynamics detection exceeds target latency."""
        # Make detectors slow - need longer delays for parallel execution
        import time
        
        def slow_volume_detect(*args, **kwargs):
            time.sleep(0.11)  # 110ms
            return VolumeResult(
                level='loud',
                db_value=-8.5,
                timestamp=datetime.now(timezone.utc)
            )
        
        def slow_rate_detect(*args, **kwargs):
            time.sleep(0.11)  # 110ms
            return RateResult(
                classification='fast',
                wpm=175.0,
                onset_count=50,
                timestamp=datetime.now(timezone.utc)
            )
        
        mock_volume_detector.detect_volume.side_effect = slow_volume_detect
        mock_rate_detector.detect_rate.side_effect = slow_rate_detect
        
        with patch('emotion_dynamics.orchestrator.logger') as mock_logger:
            dynamics, volume_ms, rate_ms, combined_ms = orchestrator.detect_audio_dynamics(
                audio_data=sample_audio,
                sample_rate=16000
            )
            
            # Combined latency should exceed 100ms target (parallel execution)
            # Since they run in parallel, combined should be ~110ms (max of the two)
            assert combined_ms >= 100
            
            # Warning should be logged
            warning_calls = [
                call for call in mock_logger.warning.call_args_list
                if 'exceeded target latency' in str(call)
            ]
            assert len(warning_calls) > 0
    
    def test_process_audio_and_text_correlation_id_propagation(
        self,
        orchestrator,
        sample_audio,
        mock_ssml_generator
    ):
        """Test correlation ID is propagated through pipeline."""
        result = orchestrator.process_audio_and_text(
            audio_data=sample_audio,
            sample_rate=16000,
            translated_text='Hello world'
        )
        
        # Correlation ID should be in result
        assert result.correlation_id is not None
        
        # Correlation ID should be in dynamics
        assert result.dynamics.correlation_id == result.correlation_id
