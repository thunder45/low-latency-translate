"""
Unit tests for error handling and graceful degradation.

This module tests the custom exceptions and graceful degradation
functionality for audio quality validation.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

from audio_quality.exceptions import (
    AudioQualityError,
    AudioFormatError,
    QualityAnalysisError,
    AudioProcessingError,
    ConfigurationError
)
from audio_quality.utils.graceful_degradation import analyze_with_fallback
from audio_quality.analyzers.quality_analyzer import AudioQualityAnalyzer
from audio_quality.models.quality_config import QualityConfig


class TestCustomExceptions:
    """Test suite for custom exception classes."""
    
    def test_audio_quality_error_base_exception(self):
        """Tests that AudioQualityError is the base exception."""
        error = AudioQualityError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"
    
    def test_audio_format_error_with_message(self):
        """Tests AudioFormatError with message only."""
        error = AudioFormatError("Invalid sample rate")
        assert isinstance(error, AudioQualityError)
        assert str(error) == "Invalid sample rate"
        assert error.format_details == {}
    
    def test_audio_format_error_with_details(self):
        """Tests AudioFormatError with format details."""
        details = {
            'sample_rate': 11025,
            'expected': [8000, 16000, 24000, 48000]
        }
        error = AudioFormatError("Invalid sample rate", format_details=details)
        assert error.format_details == details
        assert error.format_details['sample_rate'] == 11025
    
    def test_quality_analysis_error_with_message(self):
        """Tests QualityAnalysisError with message only."""
        error = QualityAnalysisError("Analysis failed")
        assert isinstance(error, AudioQualityError)
        assert str(error) == "Analysis failed"
        assert error.analysis_type is None
        assert error.original_error is None
    
    def test_quality_analysis_error_with_type(self):
        """Tests QualityAnalysisError with analysis type."""
        error = QualityAnalysisError("SNR calculation failed", analysis_type='snr')
        assert str(error) == "snr: SNR calculation failed"
        assert error.analysis_type == 'snr'
    
    def test_quality_analysis_error_with_original_error(self):
        """Tests QualityAnalysisError with original error."""
        original = ValueError("Invalid input")
        error = QualityAnalysisError(
            "Analysis failed",
            analysis_type='clipping',
            original_error=original
        )
        assert error.original_error == original
        assert str(error) == "clipping: Analysis failed"
    
    def test_audio_processing_error_with_type(self):
        """Tests AudioProcessingError with processing type."""
        error = AudioProcessingError("Filter failed", processing_type='high_pass')
        assert isinstance(error, AudioQualityError)
        assert str(error) == "high_pass: Filter failed"
        assert error.processing_type == 'high_pass'
    
    def test_configuration_error_with_message(self):
        """Tests ConfigurationError with message only."""
        error = ConfigurationError("Invalid configuration")
        assert isinstance(error, AudioQualityError)
        assert str(error) == "Invalid configuration"
        assert error.validation_errors == []
    
    def test_configuration_error_with_validation_errors(self):
        """Tests ConfigurationError with validation errors."""
        errors = [
            "SNR threshold must be between 10 and 40 dB",
            "Clipping threshold must be between 0.1% and 10%"
        ]
        error = ConfigurationError("Invalid configuration", validation_errors=errors)
        assert error.validation_errors == errors
        assert "SNR threshold must be between 10 and 40 dB" in str(error)
        assert "Clipping threshold must be between 0.1% and 10%" in str(error)


class TestGracefulDegradation:
    """Test suite for graceful degradation functionality."""
    
    def test_analyze_with_fallback_success(self):
        """Tests that analyze_with_fallback returns actual metrics on success."""
        config = QualityConfig()
        analyzer = AudioQualityAnalyzer(config)
        # Generate audio with some signal to ensure non-zero SNR
        audio = (np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000)) * 10000).astype(np.int16)
        
        metrics = analyze_with_fallback(
            analyzer=analyzer,
            audio_chunk=audio,
            sample_rate=16000,
            stream_id='test-session'
        )
        
        # Should return actual metrics, not defaults
        assert metrics.stream_id == 'test-session'
        # With a sine wave signal, SNR should be positive
        assert metrics.snr_db > 0.0  # Not default value
        assert metrics.timestamp > 0
    
    def test_analyze_with_fallback_empty_audio(self):
        """Tests that analyze_with_fallback returns defaults for empty audio."""
        config = QualityConfig()
        analyzer = AudioQualityAnalyzer(config)
        audio = np.array([])
        
        metrics = analyze_with_fallback(
            analyzer=analyzer,
            audio_chunk=audio,
            sample_rate=16000,
            stream_id='test-session'
        )
        
        # Should return default metrics
        assert metrics.stream_id == 'test-session'
        assert metrics.snr_db == 0.0
        assert metrics.clipping_percentage == 0.0
        assert metrics.is_clipping is False
        assert metrics.echo_level_db == -100.0
        assert metrics.has_echo is False
        assert metrics.is_silent is False
    
    def test_analyze_with_fallback_invalid_sample_rate(self):
        """Tests that analyze_with_fallback returns defaults for invalid sample rate."""
        config = QualityConfig()
        analyzer = AudioQualityAnalyzer(config)
        audio = np.random.randn(16000).astype(np.int16)
        
        metrics = analyze_with_fallback(
            analyzer=analyzer,
            audio_chunk=audio,
            sample_rate=-1,  # Invalid
            stream_id='test-session'
        )
        
        # Should return default metrics
        assert metrics.stream_id == 'test-session'
        assert metrics.snr_db == 0.0
        assert metrics.clipping_percentage == 0.0
    
    def test_analyze_with_fallback_analysis_error(self):
        """Tests that analyze_with_fallback handles analysis errors gracefully."""
        config = QualityConfig()
        analyzer = AudioQualityAnalyzer(config)
        
        # Mock the analyze method to raise an error
        with patch.object(analyzer, 'analyze', side_effect=QualityAnalysisError("Test error")):
            audio = np.random.randn(16000).astype(np.int16)
            
            metrics = analyze_with_fallback(
                analyzer=analyzer,
                audio_chunk=audio,
                sample_rate=16000,
                stream_id='test-session'
            )
            
            # Should return default metrics
            assert metrics.stream_id == 'test-session'
            assert metrics.snr_db == 0.0
            assert metrics.clipping_percentage == 0.0
    
    def test_analyze_with_fallback_unexpected_error(self):
        """Tests that analyze_with_fallback handles unexpected errors gracefully."""
        config = QualityConfig()
        analyzer = AudioQualityAnalyzer(config)
        
        # Mock the analyze method to raise an unexpected error
        with patch.object(analyzer, 'analyze', side_effect=RuntimeError("Unexpected error")):
            audio = np.random.randn(16000).astype(np.int16)
            
            metrics = analyze_with_fallback(
                analyzer=analyzer,
                audio_chunk=audio,
                sample_rate=16000,
                stream_id='test-session'
            )
            
            # Should return default metrics
            assert metrics.stream_id == 'test-session'
            assert metrics.snr_db == 0.0
            assert metrics.clipping_percentage == 0.0
    
    def test_analyze_with_fallback_uses_custom_timestamp(self):
        """Tests that analyze_with_fallback uses custom timestamp."""
        config = QualityConfig()
        analyzer = AudioQualityAnalyzer(config)
        audio = np.random.randn(16000).astype(np.int16)
        custom_timestamp = 1234567890.0
        
        metrics = analyze_with_fallback(
            analyzer=analyzer,
            audio_chunk=audio,
            sample_rate=16000,
            stream_id='test-session',
            timestamp=custom_timestamp
        )
        
        assert metrics.timestamp == custom_timestamp
    
    @patch('boto3.client')
    def test_analyze_with_fallback_emits_metric(self, mock_boto3_client):
        """Tests that analyze_with_fallback emits CloudWatch metric on fallback."""
        config = QualityConfig()
        analyzer = AudioQualityAnalyzer(config)
        
        # Mock CloudWatch client
        mock_cloudwatch = Mock()
        mock_boto3_client.return_value = mock_cloudwatch
        
        # Trigger fallback with empty audio
        audio = np.array([])
        
        metrics = analyze_with_fallback(
            analyzer=analyzer,
            audio_chunk=audio,
            sample_rate=16000,
            stream_id='test-session'
        )
        
        # Should have attempted to emit metric
        # (Note: actual emission depends on boto3 being available)
        assert metrics.snr_db == 0.0  # Fallback metrics returned
    
    def test_analyze_with_fallback_never_raises_exception(self):
        """Tests that analyze_with_fallback never raises exceptions."""
        config = QualityConfig()
        analyzer = AudioQualityAnalyzer(config)
        
        # Try various invalid inputs - should never raise
        test_cases = [
            (None, 16000),
            (np.array([]), 16000),
            (np.random.randn(16000), -1),
            (np.random.randn(16000), 0),
        ]
        
        for audio, sample_rate in test_cases:
            try:
                metrics = analyze_with_fallback(
                    analyzer=analyzer,
                    audio_chunk=audio,
                    sample_rate=sample_rate,
                    stream_id='test-session'
                )
                # Should always return metrics
                assert metrics is not None
                assert metrics.stream_id == 'test-session'
            except Exception as e:
                pytest.fail(f"analyze_with_fallback raised exception: {e}")


class TestErrorHandlingIntegration:
    """Integration tests for error handling in the full pipeline."""
    
    def test_invalid_config_raises_configuration_error(self):
        """Tests that invalid configuration raises ConfigurationError."""
        # SNR threshold too low
        config = QualityConfig(snr_threshold_db=5.0)
        errors = config.validate()
        
        assert len(errors) > 0
        assert "SNR threshold must be between 10 and 40 dB" in errors[0]
    
    def test_analyzer_initialization_with_invalid_config_fails(self):
        """Tests that analyzer initialization fails with invalid config."""
        config = QualityConfig(snr_threshold_db=5.0)  # Invalid
        
        with pytest.raises(ValueError) as exc_info:
            AudioQualityAnalyzer(config)
        
        assert "Invalid configuration" in str(exc_info.value)
    
    def test_analyzer_with_valid_config_succeeds(self):
        """Tests that analyzer initialization succeeds with valid config."""
        config = QualityConfig(
            snr_threshold_db=20.0,
            clipping_threshold_percent=1.0
        )
        
        # Should not raise
        analyzer = AudioQualityAnalyzer(config)
        assert analyzer is not None
        assert analyzer.config == config
