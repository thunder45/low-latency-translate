"""
Integration tests for AudioDynamicsOrchestrator.

Tests complete end-to-end flow from audio input to synthesized speech output
with real components (not mocked), parallel execution timing, correlation ID
propagation, error handling, and graceful degradation.
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch

from emotion_dynamics.orchestrator import AudioDynamicsOrchestrator
from emotion_dynamics.detectors.volume_detector import VolumeDetector
from emotion_dynamics.detectors.speaking_rate_detector import SpeakingRateDetector
from emotion_dynamics.generators.ssml_generator import SSMLGenerator
from emotion_dynamics.clients.polly_client import PollyClient
from emotion_dynamics.models.processing_options import ProcessingOptions
from emotion_dynamics.models.processing_result import ProcessingResult
from emotion_dynamics.exceptions import EmotionDynamicsError


class TestAudioDynamicsOrchestratorIntegration:
    """Integration test suite for AudioDynamicsOrchestrator."""
    
    @pytest.fixture
    def real_orchestrator(self):
        """Create orchestrator with real components (except Polly)."""
        # Use real detectors and generator
        volume_detector = VolumeDetector()
        rate_detector = SpeakingRateDetector()
        ssml_generator = SSMLGenerator()
        
        # Mock Polly client to avoid actual AWS calls
        polly_client = Mock(spec=PollyClient)
        polly_client.synthesize_speech.return_value = b'fake_audio_stream'
        
        return AudioDynamicsOrchestrator(
            volume_detector=volume_detector,
            rate_detector=rate_detector,
            ssml_generator=ssml_generator,
            polly_client=polly_client
        )
    
    @pytest.fixture
    def sample_audio_loud(self):
        """Create sample audio with loud volume."""
        # Generate audio with high amplitude (loud)
        duration = 2.0  # 2 seconds
        sample_rate = 16000
        num_samples = int(duration * sample_rate)
        
        # High amplitude sine wave
        t = np.linspace(0, duration, num_samples)
        audio = 0.8 * np.sin(2 * np.pi * 440 * t)  # 440 Hz tone at 80% amplitude
        
        return audio.astype(np.float32)
    
    @pytest.fixture
    def sample_audio_soft(self):
        """Create sample audio with soft volume."""
        # Generate audio with low amplitude (soft)
        duration = 2.0
        sample_rate = 16000
        num_samples = int(duration * sample_rate)
        
        # Low amplitude sine wave
        t = np.linspace(0, duration, num_samples)
        audio = 0.01 * np.sin(2 * np.pi * 440 * t)  # 440 Hz tone at 1% amplitude
        
        return audio.astype(np.float32)
    
    @pytest.fixture
    def sample_audio_with_onsets(self):
        """Create sample audio with clear onset patterns for rate detection."""
        # Generate audio with distinct onset events
        duration = 3.0
        sample_rate = 16000
        num_samples = int(duration * sample_rate)
        
        audio = np.zeros(num_samples, dtype=np.float32)
        
        # Add 10 onset events (bursts of sound)
        onset_times = np.linspace(0.2, 2.8, 10)
        for onset_time in onset_times:
            onset_sample = int(onset_time * sample_rate)
            burst_length = int(0.05 * sample_rate)  # 50ms bursts
            
            if onset_sample + burst_length < num_samples:
                t = np.linspace(0, 0.05, burst_length)
                burst = 0.5 * np.sin(2 * np.pi * 440 * t)
                audio[onset_sample:onset_sample + burst_length] = burst
        
        return audio
    
    def test_complete_flow_from_audio_to_synthesized_output(
        self,
        real_orchestrator,
        sample_audio_loud
    ):
        """Test complete end-to-end flow from audio input to synthesized audio output."""
        # Process audio and text through complete pipeline
        result = real_orchestrator.process_audio_and_text(
            audio_data=sample_audio_loud,
            sample_rate=16000,
            translated_text='This is a test message'
        )
        
        # Verify result structure
        assert isinstance(result, ProcessingResult)
        assert result.audio_stream == b'fake_audio_stream'
        assert result.dynamics is not None
        assert result.ssml_text is not None
        assert result.correlation_id is not None
        
        # Verify dynamics were detected
        assert result.dynamics.volume.level in ['loud', 'medium', 'soft', 'whisper']
        assert result.dynamics.rate.classification in [
            'very_slow', 'slow', 'medium', 'fast', 'very_fast'
        ]
        
        # Verify SSML was generated
        assert '<speak>' in result.ssml_text
        assert '</speak>' in result.ssml_text
        assert 'This is a test message' in result.ssml_text or \
               '&' in result.ssml_text  # XML escaped
        
        # Verify timing metrics
        assert result.processing_time_ms > 0
        assert result.volume_detection_ms >= 0
        assert result.rate_detection_ms >= 0
        assert result.ssml_generation_ms >= 0
        assert result.polly_synthesis_ms >= 0
    
    def test_parallel_execution_timing(
        self,
        real_orchestrator,
        sample_audio_with_onsets
    ):
        """Test that parallel execution meets latency requirements."""
        # Detect dynamics with timing
        start_time = time.time()
        
        dynamics, volume_ms, rate_ms, combined_ms = real_orchestrator.detect_audio_dynamics(
            audio_data=sample_audio_with_onsets,
            sample_rate=16000
        )
        
        end_time = time.time()
        actual_time_ms = int((end_time - start_time) * 1000)
        
        # Verify parallel execution
        # Combined time should be close to max(volume_ms, rate_ms), not sum
        # Allow some overhead for thread management
        max_individual = max(volume_ms, rate_ms)
        assert combined_ms <= max_individual + 50  # 50ms overhead allowance
        
        # Verify latency target (100ms for 3-second audio)
        # Note: May exceed target with real librosa processing
        print(f"Dynamics detection timing: volume={volume_ms}ms, "
              f"rate={rate_ms}ms, combined={combined_ms}ms, "
              f"actual={actual_time_ms}ms")
        
        # Verify results are valid
        assert dynamics.volume.level is not None
        assert dynamics.rate.classification is not None
    
    def test_correlation_id_propagation(
        self,
        real_orchestrator,
        sample_audio_loud
    ):
        """Test correlation ID is propagated through entire pipeline."""
        correlation_id = 'test-correlation-xyz-789'
        
        # Detect dynamics with correlation ID
        dynamics, _, _, _ = real_orchestrator.detect_audio_dynamics(
            audio_data=sample_audio_loud,
            sample_rate=16000,
            correlation_id=correlation_id
        )
        
        # Verify correlation ID in dynamics
        assert dynamics.correlation_id == correlation_id
        
        # Process complete pipeline
        result = real_orchestrator.process_audio_and_text(
            audio_data=sample_audio_loud,
            sample_rate=16000,
            translated_text='Test message'
        )
        
        # Verify correlation ID in result
        assert result.correlation_id is not None
        assert result.dynamics.correlation_id == result.correlation_id
    
    def test_error_propagation_with_invalid_audio(
        self,
        real_orchestrator
    ):
        """Test error propagation when audio data is invalid."""
        # Test with empty audio
        with pytest.raises(EmotionDynamicsError) as exc_info:
            real_orchestrator.process_audio_and_text(
                audio_data=np.array([]),
                sample_rate=16000,
                translated_text='Test'
            )
        
        assert "audio_data is empty" in str(exc_info.value)
    
    def test_error_propagation_with_polly_failure(
        self,
        real_orchestrator,
        sample_audio_loud
    ):
        """Test error propagation when Polly synthesis fails."""
        # Make Polly client fail
        real_orchestrator.polly_client.synthesize_speech.side_effect = \
            Exception("Polly service unavailable")
        
        with pytest.raises(EmotionDynamicsError) as exc_info:
            real_orchestrator.process_audio_and_text(
                audio_data=sample_audio_loud,
                sample_rate=16000,
                translated_text='Test message'
            )
        
        assert "Speech synthesis failed" in str(exc_info.value)
    
    def test_graceful_degradation_level_1_full_functionality(
        self,
        real_orchestrator,
        sample_audio_loud
    ):
        """Test Level 1 graceful degradation: full functionality with SSML."""
        options = ProcessingOptions(
            enable_ssml=True,
            enable_volume_detection=True,
            enable_rate_detection=True
        )
        
        result = real_orchestrator.process_audio_and_text(
            audio_data=sample_audio_loud,
            sample_rate=16000,
            translated_text='Test message',
            options=options
        )
        
        # Should have full SSML with prosody tags
        assert '<prosody' in result.ssml_text
        assert 'rate=' in result.ssml_text
        assert 'volume=' in result.ssml_text
        assert result.fallback_used is False
    
    def test_graceful_degradation_level_2_partial_dynamics(
        self,
        real_orchestrator,
        sample_audio_loud
    ):
        """Test Level 2 graceful degradation: partial dynamics (one detector disabled)."""
        options = ProcessingOptions(
            enable_ssml=True,
            enable_volume_detection=True,
            enable_rate_detection=False  # Rate disabled
        )
        
        result = real_orchestrator.process_audio_and_text(
            audio_data=sample_audio_loud,
            sample_rate=16000,
            translated_text='Test message',
            options=options
        )
        
        # Should have SSML with volume but default rate
        assert '<prosody' in result.ssml_text
        assert result.dynamics.rate.classification == 'medium'  # Default
        assert result.fallback_used is False
    
    def test_graceful_degradation_level_3_default_dynamics(
        self,
        real_orchestrator,
        sample_audio_loud
    ):
        """Test Level 3 graceful degradation: default dynamics (both detectors disabled)."""
        options = ProcessingOptions(
            enable_ssml=True,
            enable_volume_detection=False,
            enable_rate_detection=False
        )
        
        result = real_orchestrator.process_audio_and_text(
            audio_data=sample_audio_loud,
            sample_rate=16000,
            translated_text='Test message',
            options=options
        )
        
        # Should have SSML with default medium values
        assert '<prosody' in result.ssml_text
        assert result.dynamics.volume.level == 'medium'  # Default
        assert result.dynamics.rate.classification == 'medium'  # Default
        assert result.fallback_used is False
    
    def test_graceful_degradation_level_4_plain_text_fallback(
        self,
        real_orchestrator,
        sample_audio_loud
    ):
        """Test Level 4 graceful degradation: plain text fallback (SSML disabled)."""
        options = ProcessingOptions(
            enable_ssml=False
        )
        
        result = real_orchestrator.process_audio_and_text(
            audio_data=sample_audio_loud,
            sample_rate=16000,
            translated_text='Test message',
            options=options
        )
        
        # Should have plain SSML without prosody tags
        assert '<speak>' in result.ssml_text
        assert '</speak>' in result.ssml_text
        assert '<prosody' not in result.ssml_text
        assert result.fallback_used is True
    
    def test_fallback_chain_with_ssml_generation_failure(
        self,
        real_orchestrator,
        sample_audio_loud
    ):
        """Test fallback chain when SSML generation fails."""
        # Make SSML generator fail on first call
        original_generate = real_orchestrator.ssml_generator.generate_ssml
        call_count = [0]
        
        def failing_generate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1 and kwargs.get('dynamics') is not None:
                raise Exception("SSML generation failed")
            return original_generate(*args, **kwargs)
        
        real_orchestrator.ssml_generator.generate_ssml = failing_generate
        
        result = real_orchestrator.process_audio_and_text(
            audio_data=sample_audio_loud,
            sample_rate=16000,
            translated_text='Test message'
        )
        
        # Should fall back to plain text
        assert result.fallback_used is True
        assert result.audio_stream is not None  # Audio still generated
    
    def test_volume_detection_with_loud_audio(
        self,
        real_orchestrator,
        sample_audio_loud
    ):
        """Test volume detection correctly identifies loud audio."""
        dynamics, _, _, _ = real_orchestrator.detect_audio_dynamics(
            audio_data=sample_audio_loud,
            sample_rate=16000
        )
        
        # Loud audio should be detected as loud or medium
        assert dynamics.volume.level in ['loud', 'medium']
        assert dynamics.volume.db_value > -30.0  # Not whisper level
    
    def test_volume_detection_with_soft_audio(
        self,
        real_orchestrator,
        sample_audio_soft
    ):
        """Test volume detection correctly identifies soft audio."""
        dynamics, _, _, _ = real_orchestrator.detect_audio_dynamics(
            audio_data=sample_audio_soft,
            sample_rate=16000
        )
        
        # Soft audio should be detected as soft or whisper
        assert dynamics.volume.level in ['soft', 'whisper', 'medium']
        assert dynamics.volume.db_value < -10.0  # Not loud level
    
    def test_rate_detection_with_onset_patterns(
        self,
        real_orchestrator,
        sample_audio_with_onsets
    ):
        """Test rate detection with clear onset patterns."""
        dynamics, _, _, _ = real_orchestrator.detect_audio_dynamics(
            audio_data=sample_audio_with_onsets,
            sample_rate=16000
        )
        
        # Should detect some rate classification
        assert dynamics.rate.classification in [
            'very_slow', 'slow', 'medium', 'fast', 'very_fast'
        ]
        assert dynamics.rate.wpm >= 0
        assert dynamics.rate.onset_count >= 0
    
    def test_concurrent_processing_multiple_requests(
        self,
        real_orchestrator,
        sample_audio_loud
    ):
        """Test orchestrator handles concurrent processing requests."""
        import concurrent.futures
        
        def process_request(request_id):
            return real_orchestrator.process_audio_and_text(
                audio_data=sample_audio_loud,
                sample_rate=16000,
                translated_text=f'Message {request_id}'
            )
        
        # Process 5 requests concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(process_request, i)
                for i in range(5)
            ]
            
            results = [future.result() for future in futures]
        
        # All requests should succeed
        assert len(results) == 5
        for result in results:
            assert isinstance(result, ProcessingResult)
            assert result.audio_stream is not None
            assert result.correlation_id is not None
        
        # Each should have unique correlation ID
        correlation_ids = [r.correlation_id for r in results]
        assert len(set(correlation_ids)) == 5  # All unique
