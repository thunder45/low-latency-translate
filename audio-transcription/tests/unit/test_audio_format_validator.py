"""
Unit tests for AudioFormatValidator.

Tests validation logic for audio format specifications including
sample rate, bit depth, channel count, and encoding validation.
"""

import pytest
from audio_quality.models.audio_format import AudioFormat
from audio_quality.models.validation_result import ValidationResult
from audio_quality.validators.format_validator import AudioFormatValidator


class TestAudioFormatValidator:
    """Test suite for AudioFormatValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Fixture providing AudioFormatValidator instance."""
        return AudioFormatValidator()
    
    def test_validate_valid_format_16khz(self, validator):
        """Test validation succeeds with valid 16 kHz format."""
        audio_format = AudioFormat(
            sample_rate=16000,
            bit_depth=16,
            channels=1,
            encoding='pcm_s16le'
        )
        
        result = validator.validate(audio_format)
        
        assert result.success is True
        assert len(result.errors) == 0
        assert result.error_message == ''
        assert bool(result) is True
    
    def test_validate_valid_format_8khz(self, validator):
        """Test validation succeeds with valid 8 kHz format."""
        audio_format = AudioFormat(
            sample_rate=8000,
            bit_depth=16,
            channels=1,
            encoding='pcm_s16le'
        )
        
        result = validator.validate(audio_format)
        
        assert result.success is True
        assert len(result.errors) == 0
    
    def test_validate_valid_format_24khz(self, validator):
        """Test validation succeeds with valid 24 kHz format."""
        audio_format = AudioFormat(
            sample_rate=24000,
            bit_depth=16,
            channels=1,
            encoding='pcm_s16le'
        )
        
        result = validator.validate(audio_format)
        
        assert result.success is True
        assert len(result.errors) == 0
    
    def test_validate_valid_format_48khz(self, validator):
        """Test validation succeeds with valid 48 kHz format."""
        audio_format = AudioFormat(
            sample_rate=48000,
            bit_depth=16,
            channels=1,
            encoding='pcm_s16le'
        )
        
        result = validator.validate(audio_format)
        
        assert result.success is True
        assert len(result.errors) == 0
    
    def test_validate_invalid_sample_rate(self, validator):
        """Test validation fails with unsupported sample rate."""
        audio_format = AudioFormat(
            sample_rate=44100,  # CD quality, not supported
            bit_depth=16,
            channels=1,
            encoding='pcm_s16le'
        )
        
        result = validator.validate(audio_format)
        
        assert result.success is False
        assert len(result.errors) == 1
        assert '44100 Hz not supported' in result.errors[0]
        assert '[8000, 16000, 24000, 48000]' in result.errors[0]
        assert bool(result) is False
    
    def test_validate_invalid_bit_depth(self, validator):
        """Test validation fails with unsupported bit depth."""
        audio_format = AudioFormat(
            sample_rate=16000,
            bit_depth=24,  # 24-bit not supported
            channels=1,
            encoding='pcm_s16le'
        )
        
        result = validator.validate(audio_format)
        
        assert result.success is False
        assert len(result.errors) == 1
        assert '24 bits not supported' in result.errors[0]
        assert '[16]' in result.errors[0]
    
    def test_validate_invalid_channels(self, validator):
        """Test validation fails with unsupported channel count."""
        audio_format = AudioFormat(
            sample_rate=16000,
            bit_depth=16,
            channels=2,  # Stereo not supported
            encoding='pcm_s16le'
        )
        
        result = validator.validate(audio_format)
        
        assert result.success is False
        assert len(result.errors) == 1
        assert '2 not supported' in result.errors[0]
        assert 'mono only' in result.errors[0].lower()
    
    def test_validate_invalid_encoding(self, validator):
        """Test validation fails with unsupported encoding."""
        audio_format = AudioFormat(
            sample_rate=16000,
            bit_depth=16,
            channels=1,
            encoding='mp3'  # MP3 not supported
        )
        
        result = validator.validate(audio_format)
        
        assert result.success is False
        assert len(result.errors) == 1
        assert 'mp3' in result.errors[0].lower()
        assert 'pcm_s16le' in result.errors[0]
    
    def test_validate_multiple_invalid_parameters(self, validator):
        """Test validation fails with multiple invalid parameters."""
        audio_format = AudioFormat(
            sample_rate=44100,  # Invalid
            bit_depth=24,       # Invalid
            channels=2,         # Invalid
            encoding='mp3'      # Invalid
        )
        
        result = validator.validate(audio_format)
        
        assert result.success is False
        assert len(result.errors) == 4
        assert any('44100' in error for error in result.errors)
        assert any('24 bits' in error for error in result.errors)
        assert any('2 not supported' in error for error in result.errors)
        assert any('mp3' in error.lower() for error in result.errors)
    
    def test_validate_edge_case_zero_sample_rate(self, validator):
        """Test validation fails with zero sample rate."""
        audio_format = AudioFormat(
            sample_rate=0,
            bit_depth=16,
            channels=1,
            encoding='pcm_s16le'
        )
        
        result = validator.validate(audio_format)
        
        assert result.success is False
        assert len(result.errors) == 1
        assert '0 Hz not supported' in result.errors[0]
    
    def test_validate_edge_case_negative_bit_depth(self, validator):
        """Test validation fails with negative bit depth."""
        audio_format = AudioFormat(
            sample_rate=16000,
            bit_depth=-16,
            channels=1,
            encoding='pcm_s16le'
        )
        
        result = validator.validate(audio_format)
        
        assert result.success is False
        assert len(result.errors) == 1
        assert '-16 bits not supported' in result.errors[0]
    
    def test_validation_result_error_message_property(self, validator):
        """Test ValidationResult error_message property formats errors correctly."""
        audio_format = AudioFormat(
            sample_rate=44100,
            bit_depth=24,
            channels=1,
            encoding='pcm_s16le'
        )
        
        result = validator.validate(audio_format)
        
        error_msg = result.error_message
        assert '44100 Hz not supported' in error_msg
        assert '24 bits not supported' in error_msg
        assert '\n' in error_msg  # Errors joined by newlines
    
    def test_supported_constants_match_audio_format(self, validator):
        """Test validator constants match AudioFormat constants."""
        assert validator.SUPPORTED_SAMPLE_RATES == AudioFormat.SUPPORTED_SAMPLE_RATES
        assert validator.SUPPORTED_BIT_DEPTHS == AudioFormat.SUPPORTED_BIT_DEPTHS
        assert validator.SUPPORTED_CHANNELS == AudioFormat.SUPPORTED_CHANNELS
        assert validator.SUPPORTED_ENCODINGS == AudioFormat.SUPPORTED_ENCODINGS


class TestValidationResult:
    """Test suite for ValidationResult dataclass."""
    
    def test_success_result_factory(self):
        """Test ValidationResult.success_result() factory method."""
        result = ValidationResult.success_result()
        
        assert result.success is True
        assert result.errors == []
        assert bool(result) is True
        assert result.error_message == ''
    
    def test_failure_result_factory(self):
        """Test ValidationResult.failure_result() factory method."""
        errors = ['Error 1', 'Error 2']
        result = ValidationResult.failure_result(errors)
        
        assert result.success is False
        assert result.errors == errors
        assert bool(result) is False
        assert 'Error 1' in result.error_message
        assert 'Error 2' in result.error_message
    
    def test_boolean_conversion_success(self):
        """Test ValidationResult can be used in boolean context (success)."""
        result = ValidationResult(success=True, errors=[])
        
        if result:
            assert True
        else:
            pytest.fail('ValidationResult should evaluate to True')
    
    def test_boolean_conversion_failure(self):
        """Test ValidationResult can be used in boolean context (failure)."""
        result = ValidationResult(success=False, errors=['Error'])
        
        if not result:
            assert True
        else:
            pytest.fail('ValidationResult should evaluate to False')
    
    def test_error_message_empty_for_success(self):
        """Test error_message is empty string for successful validation."""
        result = ValidationResult(success=True, errors=[])
        
        assert result.error_message == ''
    
    def test_error_message_single_error(self):
        """Test error_message with single error."""
        result = ValidationResult(success=False, errors=['Single error'])
        
        assert result.error_message == 'Single error'
    
    def test_error_message_multiple_errors(self):
        """Test error_message joins multiple errors with newlines."""
        errors = ['Error 1', 'Error 2', 'Error 3']
        result = ValidationResult(success=False, errors=errors)
        
        expected = 'Error 1\nError 2\nError 3'
        assert result.error_message == expected
