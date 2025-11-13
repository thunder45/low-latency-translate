"""Unit tests for SSMLGenerator."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

from emotion_dynamics.generators.ssml_generator import SSMLGenerator
from emotion_dynamics.models.audio_dynamics import AudioDynamics
from emotion_dynamics.models.volume_result import VolumeResult
from emotion_dynamics.models.rate_result import RateResult
from emotion_dynamics.exceptions import SSMLValidationError


class TestSSMLGenerator:
    """Test suite for SSMLGenerator."""
    
    @pytest.fixture
    def generator(self):
        """Fixture for SSMLGenerator instance."""
        return SSMLGenerator()
    
    @pytest.fixture
    def sample_dynamics(self):
        """Fixture for sample AudioDynamics."""
        volume = VolumeResult(
            level='medium',
            db_value=-15.0,
            timestamp=datetime.now(timezone.utc)
        )
        rate = RateResult(
            classification='medium',
            wpm=145.0,
            onset_count=50,
            timestamp=datetime.now(timezone.utc)
        )
        return AudioDynamics(
            volume=volume,
            rate=rate,
            correlation_id='test-correlation-123'
        )
    
    def test_initialization_success(self):
        """Test successful initialization of SSMLGenerator."""
        generator = SSMLGenerator()
        assert generator is not None
        assert hasattr(generator, 'VALID_VOLUME_VALUES')
        assert hasattr(generator, 'VALID_RATE_VALUES')
    
    def test_generate_ssml_with_medium_volume_and_rate(self, generator, sample_dynamics):
        """Test SSML generation with medium volume and medium rate."""
        text = "Hello, world!"
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        assert '<speak>' in ssml
        assert '</speak>' in ssml
        assert '<prosody' in ssml
        assert 'rate="medium"' in ssml
        assert 'volume="medium"' in ssml
        assert 'Hello, world!' in ssml
    
    def test_prosody_mapping_loud_volume(self, generator):
        """Test prosody mapping for loud volume level."""
        volume = VolumeResult(level='loud', db_value=-5.0, timestamp=datetime.now(timezone.utc))
        rate = RateResult(classification='medium', wpm=145.0, onset_count=50, timestamp=datetime.now(timezone.utc))
        dynamics = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
        
        ssml = generator.generate_ssml("Test text", dynamics)
        
        assert 'volume="x-loud"' in ssml
    
    def test_prosody_mapping_soft_volume(self, generator):
        """Test prosody mapping for soft volume level."""
        volume = VolumeResult(level='soft', db_value=-25.0, timestamp=datetime.now(timezone.utc))
        rate = RateResult(classification='medium', wpm=145.0, onset_count=50, timestamp=datetime.now(timezone.utc))
        dynamics = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
        
        ssml = generator.generate_ssml("Test text", dynamics)
        
        assert 'volume="soft"' in ssml
    
    def test_prosody_mapping_whisper_volume(self, generator):
        """Test prosody mapping for whisper volume level."""
        volume = VolumeResult(level='whisper', db_value=-35.0, timestamp=datetime.now(timezone.utc))
        rate = RateResult(classification='medium', wpm=145.0, onset_count=50, timestamp=datetime.now(timezone.utc))
        dynamics = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
        
        ssml = generator.generate_ssml("Test text", dynamics)
        
        assert 'volume="x-soft"' in ssml
    
    def test_prosody_mapping_very_slow_rate(self, generator):
        """Test prosody mapping for very slow speaking rate."""
        volume = VolumeResult(level='medium', db_value=-15.0, timestamp=datetime.now(timezone.utc))
        rate = RateResult(classification='very_slow', wpm=80.0, onset_count=20, timestamp=datetime.now(timezone.utc))
        dynamics = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
        
        ssml = generator.generate_ssml("Test text", dynamics)
        
        assert 'rate="x-slow"' in ssml
    
    def test_prosody_mapping_slow_rate(self, generator):
        """Test prosody mapping for slow speaking rate."""
        volume = VolumeResult(level='medium', db_value=-15.0, timestamp=datetime.now(timezone.utc))
        rate = RateResult(classification='slow', wpm=115.0, onset_count=30, timestamp=datetime.now(timezone.utc))
        dynamics = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
        
        ssml = generator.generate_ssml("Test text", dynamics)
        
        assert 'rate="slow"' in ssml
    
    def test_prosody_mapping_fast_rate(self, generator):
        """Test prosody mapping for fast speaking rate."""
        volume = VolumeResult(level='medium', db_value=-15.0, timestamp=datetime.now(timezone.utc))
        rate = RateResult(classification='fast', wpm=175.0, onset_count=70, timestamp=datetime.now(timezone.utc))
        dynamics = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
        
        ssml = generator.generate_ssml("Test text", dynamics)
        
        assert 'rate="fast"' in ssml
    
    def test_prosody_mapping_very_fast_rate(self, generator):
        """Test prosody mapping for very fast speaking rate."""
        volume = VolumeResult(level='medium', db_value=-15.0, timestamp=datetime.now(timezone.utc))
        rate = RateResult(classification='very_fast', wpm=200.0, onset_count=80, timestamp=datetime.now(timezone.utc))
        dynamics = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
        
        ssml = generator.generate_ssml("Test text", dynamics)
        
        assert 'rate="x-fast"' in ssml
    
    def test_ssml_xml_structure_validity(self, generator, sample_dynamics):
        """Test that generated SSML has valid XML structure."""
        text = "Test text"
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        # Should parse without error
        root = ET.fromstring(ssml)
        assert root.tag == 'speak'
        
        # Should have prosody child
        prosody = root.find('.//prosody')
        assert prosody is not None
        assert 'rate' in prosody.attrib
        assert 'volume' in prosody.attrib
    
    def test_special_character_escaping_ampersand(self, generator, sample_dynamics):
        """Test XML character escaping for ampersand."""
        text = "Tom & Jerry"
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        assert '&amp;' in ssml
        assert 'Tom & Jerry' not in ssml  # Raw ampersand should be escaped
        
        # Should parse as valid XML
        root = ET.fromstring(ssml)
        assert root is not None
    
    def test_special_character_escaping_less_than(self, generator, sample_dynamics):
        """Test XML character escaping for less than symbol."""
        text = "Value < 10"
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        assert '&lt;' in ssml
        
        # Should parse as valid XML
        root = ET.fromstring(ssml)
        assert root is not None
    
    def test_special_character_escaping_greater_than(self, generator, sample_dynamics):
        """Test XML character escaping for greater than symbol."""
        text = "Value > 10"
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        assert '&gt;' in ssml
        
        # Should parse as valid XML
        root = ET.fromstring(ssml)
        assert root is not None
    
    def test_special_character_escaping_quotes(self, generator, sample_dynamics):
        """Test XML character escaping for quotes."""
        text = 'He said "Hello" and she said \'Hi\''
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        assert '&quot;' in ssml or '&apos;' in ssml
        
        # Should parse as valid XML
        root = ET.fromstring(ssml)
        assert root is not None
    
    def test_special_character_escaping_multiple(self, generator, sample_dynamics):
        """Test XML character escaping with multiple special characters."""
        text = "Tom & Jerry: <Episode> \"The Chase\" 'Part 1'"
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        assert '&amp;' in ssml
        assert '&lt;' in ssml
        assert '&gt;' in ssml
        assert '&quot;' in ssml
        assert '&apos;' in ssml
        
        # Should parse as valid XML
        root = ET.fromstring(ssml)
        assert root is not None
    
    def test_fallback_to_plain_text_on_validation_error(self, generator):
        """Test fallback to plain text when SSML validation fails."""
        # Create dynamics with invalid attributes (mock to force validation error)
        volume = VolumeResult(level='medium', db_value=-15.0, timestamp=datetime.now(timezone.utc))
        rate = RateResult(classification='medium', wpm=145.0, onset_count=50, timestamp=datetime.now(timezone.utc))
        dynamics = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
        
        # Mock to_ssml_attributes to return invalid values
        with patch.object(dynamics, 'to_ssml_attributes', return_value={'volume': 'invalid', 'rate': 'medium'}):
            # Should raise SSMLValidationError
            with pytest.raises(SSMLValidationError):
                generator.generate_ssml("Test text", dynamics)
    
    def test_handling_none_dynamics(self, generator):
        """Test handling of None dynamics (returns plain SSML)."""
        text = "Test text"
        
        ssml = generator.generate_ssml(text, None)
        
        assert '<speak>' in ssml
        assert '</speak>' in ssml
        assert '<prosody' not in ssml  # No prosody tags
        assert 'Test text' in ssml
    
    def test_handling_empty_text(self, generator, sample_dynamics):
        """Test handling of empty text."""
        ssml = generator.generate_ssml("", sample_dynamics)
        
        assert ssml == ""
    
    def test_handling_none_text(self, generator, sample_dynamics):
        """Test handling of None text."""
        ssml = generator.generate_ssml(None, sample_dynamics)
        
        assert ssml == ""
    
    def test_handling_whitespace_only_text(self, generator, sample_dynamics):
        """Test handling of whitespace-only text."""
        text = "   \n\t  "
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        # Should still generate SSML (whitespace is valid text)
        assert '<speak>' in ssml
        assert '<prosody' in ssml
    
    def test_ssml_validation_against_polly_spec(self, generator, sample_dynamics):
        """Test that generated SSML conforms to Polly specification."""
        text = "Test text for validation"
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        # Parse and validate structure
        root = ET.fromstring(ssml)
        
        # Root must be 'speak'
        assert root.tag == 'speak'
        
        # Must have prosody element
        prosody = root.find('.//prosody')
        assert prosody is not None
        
        # Prosody must have rate and volume attributes
        assert 'rate' in prosody.attrib
        assert 'volume' in prosody.attrib
        
        # Attribute values must be valid
        assert prosody.attrib['rate'] in generator.VALID_RATE_VALUES
        assert prosody.attrib['volume'] in generator.VALID_VOLUME_VALUES
    
    def test_long_text_handling(self, generator, sample_dynamics):
        """Test SSML generation with long text (3000 characters)."""
        text = "This is a test sentence. " * 120  # ~3000 characters
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        assert '<speak>' in ssml
        assert '<prosody' in ssml
        assert len(ssml) > len(text)  # SSML should be longer due to tags
        
        # Should parse as valid XML
        root = ET.fromstring(ssml)
        assert root is not None
    
    def test_unicode_text_handling(self, generator, sample_dynamics):
        """Test SSML generation with Unicode characters."""
        text = "Hello 世界! Привет мир! مرحبا بالعالم!"
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        assert '<speak>' in ssml
        assert text in ssml
        
        # Should parse as valid XML
        root = ET.fromstring(ssml)
        assert root is not None
    
    def test_newline_handling(self, generator, sample_dynamics):
        """Test SSML generation with newlines in text."""
        text = "Line 1\nLine 2\nLine 3"
        
        ssml = generator.generate_ssml(text, sample_dynamics)
        
        assert '<speak>' in ssml
        
        # Should parse as valid XML
        root = ET.fromstring(ssml)
        assert root is not None
    
    def test_all_volume_levels(self, generator):
        """Test SSML generation for all volume levels."""
        rate = RateResult(classification='medium', wpm=145.0, onset_count=50, timestamp=datetime.now(timezone.utc))
        
        volume_mappings = {
            'loud': 'x-loud',
            'medium': 'medium',
            'soft': 'soft',
            'whisper': 'x-soft'
        }
        
        for level, expected_ssml_value in volume_mappings.items():
            volume = VolumeResult(level=level, db_value=-15.0, timestamp=datetime.now(timezone.utc))
            dynamics = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
            
            ssml = generator.generate_ssml("Test", dynamics)
            
            assert f'volume="{expected_ssml_value}"' in ssml
    
    def test_all_rate_classifications(self, generator):
        """Test SSML generation for all rate classifications."""
        volume = VolumeResult(level='medium', db_value=-15.0, timestamp=datetime.now(timezone.utc))
        
        rate_mappings = {
            'very_slow': 'x-slow',
            'slow': 'slow',
            'medium': 'medium',
            'fast': 'fast',
            'very_fast': 'x-fast'
        }
        
        for classification, expected_ssml_value in rate_mappings.items():
            rate = RateResult(classification=classification, wpm=145.0, onset_count=50, timestamp=datetime.now(timezone.utc))
            dynamics = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
            
            ssml = generator.generate_ssml("Test", dynamics)
            
            assert f'rate="{expected_ssml_value}"' in ssml
    
    def test_error_handling_with_exception_in_generation(self, generator, sample_dynamics):
        """Test error handling when exception occurs during generation."""
        text = "Test text"
        
        # Mock to_ssml_attributes to raise an exception
        with patch.object(sample_dynamics, 'to_ssml_attributes', side_effect=Exception("Test error")):
            ssml = generator.generate_ssml(text, sample_dynamics)
            
            # Should fall back to plain SSML
            assert '<speak>' in ssml
            assert '<prosody' not in ssml
            assert 'Test text' in ssml
    
    def test_consistent_output_for_same_input(self, generator, sample_dynamics):
        """Test that same input produces consistent output."""
        text = "Test text"
        
        ssml1 = generator.generate_ssml(text, sample_dynamics)
        ssml2 = generator.generate_ssml(text, sample_dynamics)
        
        # Should produce identical SSML
        assert ssml1 == ssml2
    
    def test_different_correlation_ids(self, generator):
        """Test SSML generation with different correlation IDs."""
        volume = VolumeResult(level='medium', db_value=-15.0, timestamp=datetime.now(timezone.utc))
        rate = RateResult(classification='medium', wpm=145.0, onset_count=50, timestamp=datetime.now(timezone.utc))
        
        dynamics1 = AudioDynamics(volume=volume, rate=rate, correlation_id='test-123')
        dynamics2 = AudioDynamics(volume=volume, rate=rate, correlation_id='test-456')
        
        ssml1 = generator.generate_ssml("Test", dynamics1)
        ssml2 = generator.generate_ssml("Test", dynamics2)
        
        # SSML should be identical (correlation ID doesn't affect output)
        assert ssml1 == ssml2
    
    def test_plain_ssml_generation(self, generator):
        """Test plain SSML generation without prosody tags."""
        text = "Plain text"
        
        ssml = generator._generate_plain_ssml(text)
        
        assert ssml == '<speak>Plain text</speak>'
        assert '<prosody' not in ssml
    
    def test_xml_escaping_function(self, generator):
        """Test XML escaping function directly."""
        test_cases = [
            ("Tom & Jerry", "Tom &amp; Jerry"),
            ("Value < 10", "Value &lt; 10"),
            ("Value > 10", "Value &gt; 10"),
            ('Say "Hello"', 'Say &quot;Hello&quot;'),
            ("Say 'Hi'", "Say &apos;Hi&apos;"),
        ]
        
        for input_text, expected_output in test_cases:
            result = generator._escape_xml(input_text)
            assert result == expected_output
    
    def test_validate_prosody_attributes_valid(self, generator):
        """Test prosody attribute validation with valid values."""
        # Should not raise exception
        generator._validate_prosody_attributes('medium', 'medium')
        generator._validate_prosody_attributes('x-loud', 'x-fast')
        generator._validate_prosody_attributes('soft', 'slow')
    
    def test_validate_prosody_attributes_invalid_volume(self, generator):
        """Test prosody attribute validation with invalid volume."""
        with pytest.raises(SSMLValidationError) as exc_info:
            generator._validate_prosody_attributes('invalid', 'medium')
        
        assert 'Invalid volume attribute' in str(exc_info.value)
    
    def test_validate_prosody_attributes_invalid_rate(self, generator):
        """Test prosody attribute validation with invalid rate."""
        with pytest.raises(SSMLValidationError) as exc_info:
            generator._validate_prosody_attributes('medium', 'invalid')
        
        assert 'Invalid rate attribute' in str(exc_info.value)
    
    def test_validate_ssml_valid_structure(self, generator):
        """Test SSML validation with valid structure."""
        valid_ssml = '<speak><prosody rate="medium" volume="medium">Test</prosody></speak>'
        
        # Should not raise exception
        generator._validate_ssml(valid_ssml)
    
    def test_validate_ssml_invalid_root(self, generator):
        """Test SSML validation with invalid root element."""
        invalid_ssml = '<invalid><prosody rate="medium" volume="medium">Test</prosody></invalid>'
        
        with pytest.raises(SSMLValidationError) as exc_info:
            generator._validate_ssml(invalid_ssml)
        
        assert 'Root element must be' in str(exc_info.value)
    
    def test_validate_ssml_missing_rate_attribute(self, generator):
        """Test SSML validation with missing rate attribute."""
        invalid_ssml = '<speak><prosody volume="medium">Test</prosody></speak>'
        
        with pytest.raises(SSMLValidationError) as exc_info:
            generator._validate_ssml(invalid_ssml)
        
        assert 'rate' in str(exc_info.value).lower()
    
    def test_validate_ssml_missing_volume_attribute(self, generator):
        """Test SSML validation with missing volume attribute."""
        invalid_ssml = '<speak><prosody rate="medium">Test</prosody></speak>'
        
        with pytest.raises(SSMLValidationError) as exc_info:
            generator._validate_ssml(invalid_ssml)
        
        assert 'volume' in str(exc_info.value).lower()
    
    def test_validate_ssml_invalid_xml(self, generator):
        """Test SSML validation with malformed XML."""
        invalid_ssml = '<speak><prosody rate="medium" volume="medium">Test</prosody>'  # Missing closing speak tag
        
        with pytest.raises(SSMLValidationError) as exc_info:
            generator._validate_ssml(invalid_ssml)
        
        assert 'Invalid XML structure' in str(exc_info.value) or 'validation failed' in str(exc_info.value).lower()
