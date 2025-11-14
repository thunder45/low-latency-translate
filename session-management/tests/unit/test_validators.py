"""
Unit tests for validation utilities.
"""
import pytest
import json
from shared.utils.validators import (
    ValidationError,
    validate_language_code,
    validate_session_id_format,
    validate_quality_tier,
    validate_action,
    validate_message_size,
    validate_audio_chunk_size,
    validate_control_message_size
)


class TestLanguageCodeValidation:
    """Test suite for language code validation."""
    
    def test_valid_language_codes(self):
        """Test validation of valid language codes."""
        valid_codes = ['en', 'es', 'fr', 'de', 'pt', 'it', 'ja', 'ko', 'zh']
        for code in valid_codes:
            validate_language_code(code)  # Should not raise
    
    def test_empty_language_code(self):
        """Test validation of empty language code."""
        with pytest.raises(ValidationError, match="language is required"):
            validate_language_code('')
    
    def test_invalid_format(self):
        """Test validation of invalid language code format."""
        invalid_codes = ['e', 'eng', 'EN', 'e1', '12']
        for code in invalid_codes:
            with pytest.raises(ValidationError, match="must be a 2-letter ISO 639-1 code"):
                validate_language_code(code)


class TestSessionIdValidation:
    """Test suite for session ID validation."""
    
    def test_valid_session_ids(self):
        """Test validation of valid session IDs."""
        valid_ids = [
            'golden-eagle-427',
            'faithful-shepherd-001',
            'blessed-temple-999'
        ]
        for session_id in valid_ids:
            validate_session_id_format(session_id)  # Should not raise
    
    def test_empty_session_id(self):
        """Test validation of empty session ID."""
        with pytest.raises(ValidationError, match="sessionId is required"):
            validate_session_id_format('')
    
    def test_invalid_format(self):
        """Test validation of invalid session ID format."""
        invalid_ids = [
            'golden-eagle',  # Missing number
            'golden-427',  # Missing noun
            'eagle-427',  # Missing adjective
            'Golden-Eagle-427',  # Uppercase
            'golden-eagle-42',  # 2-digit number
            'golden-eagle-4270'  # 4-digit number
        ]
        for session_id in invalid_ids:
            with pytest.raises(ValidationError, match="must be in format"):
                validate_session_id_format(session_id)


class TestQualityTierValidation:
    """Test suite for quality tier validation."""
    
    def test_valid_quality_tiers(self):
        """Test validation of valid quality tiers."""
        valid_tiers = ['standard', 'premium']
        for tier in valid_tiers:
            validate_quality_tier(tier)  # Should not raise
    
    def test_empty_quality_tier(self):
        """Test validation of empty quality tier."""
        with pytest.raises(ValidationError, match="qualityTier is required"):
            validate_quality_tier('')
    
    def test_invalid_quality_tier(self):
        """Test validation of invalid quality tier."""
        invalid_tiers = ['basic', 'pro', 'Standard', 'PREMIUM']
        for tier in invalid_tiers:
            with pytest.raises(ValidationError, match="must be one of"):
                validate_quality_tier(tier)


class TestActionValidation:
    """Test suite for action validation."""
    
    def test_valid_actions(self):
        """Test validation of valid actions."""
        valid_actions = ['createSession', 'joinSession', 'refreshConnection']
        for action in valid_actions:
            validate_action(action)  # Should not raise
    
    def test_empty_action(self):
        """Test validation of empty action."""
        with pytest.raises(ValidationError, match="action is required"):
            validate_action('')
    
    def test_invalid_action(self):
        """Test validation of invalid action."""
        invalid_actions = ['sendAudio', 'pauseBroadcast', 'getStatus']
        for action in invalid_actions:
            with pytest.raises(ValidationError, match="must be one of"):
                validate_action(action)


class TestMessageSizeValidation:
    """Test suite for message size validation."""
    
    def test_valid_message_size_string(self):
        """Test validation of valid message size (string)."""
        # Small message
        validate_message_size('{"action": "createSession"}')
        
        # Medium message (10 KB)
        validate_message_size('x' * 10240)
        
        # Large message (100 KB)
        validate_message_size('x' * 102400)
    
    def test_valid_message_size_bytes(self):
        """Test validation of valid message size (bytes)."""
        validate_message_size(b'x' * 10240)
    
    def test_message_at_boundary(self):
        """Test validation of message at size boundary."""
        # Exactly 128 KB (default limit)
        validate_message_size('x' * 131072)
    
    def test_oversized_message(self):
        """Test validation of oversized message."""
        # 129 KB (exceeds default 128 KB limit)
        with pytest.raises(ValidationError, match="exceeds maximum allowed size"):
            validate_message_size('x' * 132096)
    
    def test_custom_max_size(self):
        """Test validation with custom max size."""
        # 10 KB message with 5 KB limit
        with pytest.raises(ValidationError, match="exceeds maximum allowed size"):
            validate_message_size('x' * 10240, max_size_bytes=5120)
        
        # 5 KB message with 10 KB limit
        validate_message_size('x' * 5120, max_size_bytes=10240)


class TestAudioChunkSizeValidation:
    """Test suite for audio chunk size validation."""
    
    def test_valid_audio_chunk_sizes(self):
        """Test validation of valid audio chunk sizes."""
        # Typical audio chunk (3.2 KB for 100ms at 16kHz 16-bit)
        validate_audio_chunk_size(b'\x00' * 3200)
        
        # Larger chunk (6.4 KB for 200ms)
        validate_audio_chunk_size(b'\x00' * 6400)
        
        # Maximum chunk (32 KB)
        validate_audio_chunk_size(b'\x00' * 32768)
    
    def test_audio_chunk_at_boundary(self):
        """Test validation of audio chunk at size boundary."""
        # Exactly 32 KB (default limit)
        validate_audio_chunk_size(b'\x00' * 32768)
        
        # Minimum size (100 bytes)
        validate_audio_chunk_size(b'\x00' * 100)
    
    def test_oversized_audio_chunk(self):
        """Test validation of oversized audio chunk."""
        # 33 KB (exceeds default 32 KB limit)
        with pytest.raises(ValidationError, match="exceeds maximum allowed size"):
            validate_audio_chunk_size(b'\x00' * 33792)
    
    def test_undersized_audio_chunk(self):
        """Test validation of undersized audio chunk."""
        # 50 bytes (below minimum 100 bytes)
        with pytest.raises(ValidationError, match="is too small"):
            validate_audio_chunk_size(b'\x00' * 50)
    
    def test_invalid_audio_data_type(self):
        """Test validation of invalid audio data type."""
        with pytest.raises(ValidationError, match="must be bytes"):
            validate_audio_chunk_size('not bytes')
    
    def test_custom_max_size(self):
        """Test validation with custom max size."""
        # 20 KB chunk with 10 KB limit
        with pytest.raises(ValidationError, match="exceeds maximum allowed size"):
            validate_audio_chunk_size(b'\x00' * 20480, max_size_bytes=10240)
        
        # 5 KB chunk with 10 KB limit
        validate_audio_chunk_size(b'\x00' * 5120, max_size_bytes=10240)


class TestControlMessageSizeValidation:
    """Test suite for control message size validation."""
    
    def test_valid_control_message_sizes(self):
        """Test validation of valid control message sizes."""
        # Small control message
        validate_control_message_size({'action': 'pauseBroadcast'})
        
        # Medium control message
        validate_control_message_size({
            'action': 'setVolume',
            'volumeLevel': 0.5,
            'metadata': {'timestamp': 1699500000}
        })
    
    def test_control_message_at_boundary(self):
        """Test validation of control message at size boundary."""
        # Create a payload close to 4 KB limit
        large_payload = {
            'action': 'speakerStateChange',
            'state': {
                'isPaused': False,
                'isMuted': False,
                'volume': 1.0
            },
            'metadata': 'x' * 3900  # Fill to near limit
        }
        validate_control_message_size(large_payload)
    
    def test_oversized_control_message(self):
        """Test validation of oversized control message."""
        # Create a payload exceeding 4 KB limit
        large_payload = {
            'action': 'speakerStateChange',
            'data': 'x' * 5000  # Exceeds 4 KB
        }
        with pytest.raises(ValidationError, match="exceeds maximum allowed size"):
            validate_control_message_size(large_payload)
    
    def test_invalid_control_message_payload(self):
        """Test validation of invalid control message payload."""
        # Non-serializable object
        class NonSerializable:
            pass
        
        with pytest.raises(ValidationError, match="Invalid control message payload"):
            validate_control_message_size({'obj': NonSerializable()})
    
    def test_custom_max_size(self):
        """Test validation with custom max size."""
        payload = {'action': 'test', 'data': 'x' * 2000}
        
        # Should fail with 1 KB limit
        with pytest.raises(ValidationError, match="exceeds maximum allowed size"):
            validate_control_message_size(payload, max_size_bytes=1024)
        
        # Should pass with 5 KB limit
        validate_control_message_size(payload, max_size_bytes=5120)


class TestValidationErrorDetails:
    """Test suite for ValidationError details."""
    
    def test_validation_error_with_field(self):
        """Test ValidationError with field information."""
        try:
            validate_language_code('')
        except ValidationError as e:
            assert e.field == 'language'
            assert 'required' in str(e)
    
    def test_validation_error_without_field(self):
        """Test ValidationError without field information."""
        error = ValidationError('Generic error')
        assert error.field is None
        assert str(error) == 'Generic error'
    
    def test_validation_error_message_attribute(self):
        """Test ValidationError message attribute."""
        error = ValidationError('Test message', field='testField')
        assert error.message == 'Test message'
        assert error.field == 'testField'
