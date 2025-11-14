"""Unit tests for SSML Generator."""

import pytest
from shared.services.ssml_generator import SSMLGenerator
from shared.models.emotion_dynamics import EmotionDynamics


class TestSSMLGenerator:
    """Test suite for SSMLGenerator."""
    
    @pytest.fixture
    def generator(self):
        """Create SSMLGenerator instance."""
        return SSMLGenerator()
    
    # Test XML escaping
    
    def test_escape_xml_with_ampersand(self, generator):
        """Test XML escaping handles ampersand."""
        text = "Tom & Jerry"
        escaped = generator._escape_xml(text)
        assert escaped == "Tom &amp; Jerry"
    
    def test_escape_xml_with_less_than(self, generator):
        """Test XML escaping handles less than."""
        text = "5 < 10"
        escaped = generator._escape_xml(text)
        assert escaped == "5 &lt; 10"
    
    def test_escape_xml_with_greater_than(self, generator):
        """Test XML escaping handles greater than."""
        text = "10 > 5"
        escaped = generator._escape_xml(text)
        assert escaped == "10 &gt; 5"
    
    def test_escape_xml_with_quotes(self, generator):
        """Test XML escaping handles quotes."""
        text = 'He said "hello"'
        escaped = generator._escape_xml(text)
        assert escaped == "He said &quot;hello&quot;"
    
    def test_escape_xml_with_apostrophe(self, generator):
        """Test XML escaping handles apostrophe."""
        text = "It's working"
        escaped = generator._escape_xml(text)
        assert escaped == "It&#x27;s working"
    
    def test_escape_xml_with_multiple_special_chars(self, generator):
        """Test XML escaping handles multiple special characters."""
        text = '<tag attr="value">Text & more</tag>'
        escaped = generator._escape_xml(text)
        assert "&lt;" in escaped
        assert "&gt;" in escaped
        assert "&quot;" in escaped
        assert "&amp;" in escaped
    
    # Test rate mapping
    
    def test_map_rate_slow_wpm(self, generator):
        """Test rate mapping for slow speaking rate."""
        assert generator._map_rate_to_ssml(100) == "slow"
        assert generator._map_rate_to_ssml(119) == "slow"
    
    def test_map_rate_medium_wpm(self, generator):
        """Test rate mapping for medium speaking rate."""
        assert generator._map_rate_to_ssml(120) == "medium"
        assert generator._map_rate_to_ssml(140) == "medium"
        assert generator._map_rate_to_ssml(160) == "medium"
    
    def test_map_rate_fast_wpm(self, generator):
        """Test rate mapping for fast speaking rate."""
        assert generator._map_rate_to_ssml(170) == "fast"
        assert generator._map_rate_to_ssml(185) == "fast"
        assert generator._map_rate_to_ssml(199) == "fast"
    
    def test_map_rate_very_fast_wpm(self, generator):
        """Test rate mapping for very fast speaking rate."""
        assert generator._map_rate_to_ssml(200) == "x-fast"
        assert generator._map_rate_to_ssml(250) == "x-fast"
    
    # Test volume mapping
    
    def test_map_volume_whisper(self, generator):
        """Test volume mapping for whisper."""
        assert generator._map_volume_to_ssml("whisper") == "x-soft"
    
    def test_map_volume_soft(self, generator):
        """Test volume mapping for soft."""
        assert generator._map_volume_to_ssml("soft") == "soft"
    
    def test_map_volume_normal(self, generator):
        """Test volume mapping for normal."""
        assert generator._map_volume_to_ssml("normal") == "medium"
    
    def test_map_volume_loud(self, generator):
        """Test volume mapping for loud."""
        assert generator._map_volume_to_ssml("loud") == "loud"
    
    def test_map_volume_unknown_defaults_to_medium(self, generator):
        """Test volume mapping defaults to medium for unknown values."""
        assert generator._map_volume_to_ssml("unknown") == "medium"
    
    # Test emotion emphasis
    
    def test_apply_emotion_emphasis_angry_high_intensity(self, generator):
        """Test strong emphasis for angry emotion with high intensity."""
        text = "This is important"
        result = generator._apply_emotion_emphasis(text, "angry", 0.8)
        assert result == '<emphasis level="strong">This is important</emphasis>'
    
    def test_apply_emotion_emphasis_excited_high_intensity(self, generator):
        """Test strong emphasis for excited emotion with high intensity."""
        text = "Great news"
        result = generator._apply_emotion_emphasis(text, "excited", 0.9)
        assert result == '<emphasis level="strong">Great news</emphasis>'
    
    def test_apply_emotion_emphasis_surprised_high_intensity(self, generator):
        """Test strong emphasis for surprised emotion with high intensity."""
        text = "Wow"
        result = generator._apply_emotion_emphasis(text, "surprised", 0.75)
        assert result == '<emphasis level="strong">Wow</emphasis>'
    
    def test_apply_emotion_emphasis_angry_low_intensity(self, generator):
        """Test no emphasis for angry emotion with low intensity."""
        text = "This is important"
        result = generator._apply_emotion_emphasis(text, "angry", 0.5)
        assert result == "This is important"
    
    def test_apply_emotion_emphasis_sad(self, generator):
        """Test pause for sad emotion."""
        text = "I'm sorry"
        result = generator._apply_emotion_emphasis(text, "sad", 0.6)
        assert result == '<break time="300ms"/>I\'m sorry'
    
    def test_apply_emotion_emphasis_fearful(self, generator):
        """Test pause for fearful emotion."""
        text = "Be careful"
        result = generator._apply_emotion_emphasis(text, "fearful", 0.7)
        assert result == '<break time="300ms"/>Be careful'
    
    def test_apply_emotion_emphasis_neutral(self, generator):
        """Test no emphasis for neutral emotion."""
        text = "Hello everyone"
        result = generator._apply_emotion_emphasis(text, "neutral", 0.5)
        assert result == "Hello everyone"
    
    def test_apply_emotion_emphasis_happy(self, generator):
        """Test no emphasis for happy emotion."""
        text = "Good morning"
        result = generator._apply_emotion_emphasis(text, "happy", 0.6)
        assert result == "Good morning"
    
    # Test complete SSML generation
    
    def test_generate_ssml_with_angry_loud_fast(self, generator):
        """Test SSML generation for angry, loud, fast speech."""
        dynamics = EmotionDynamics(
            emotion="angry",
            intensity=0.8,
            rate_wpm=185,
            volume_level="loud"
        )
        
        ssml = generator.generate_ssml("This is important", dynamics)
        
        assert '<speak>' in ssml
        assert '</speak>' in ssml
        assert 'rate="fast"' in ssml
        assert 'volume="loud"' in ssml
        assert '<emphasis level="strong">This is important</emphasis>' in ssml
    
    def test_generate_ssml_with_happy_normal_medium(self, generator):
        """Test SSML generation for happy, normal volume, medium rate."""
        dynamics = EmotionDynamics(
            emotion="happy",
            intensity=0.6,
            rate_wpm=140,
            volume_level="normal"
        )
        
        ssml = generator.generate_ssml("Good morning everyone", dynamics)
        
        assert '<speak>' in ssml
        assert '</speak>' in ssml
        assert 'rate="medium"' in ssml
        assert 'volume="medium"' in ssml
        assert 'Good morning everyone' in ssml
        assert '<emphasis' not in ssml  # No emphasis for happy
    
    def test_generate_ssml_with_sad_soft_slow(self, generator):
        """Test SSML generation for sad, soft, slow speech."""
        dynamics = EmotionDynamics(
            emotion="sad",
            intensity=0.5,
            rate_wpm=100,
            volume_level="soft"
        )
        
        ssml = generator.generate_ssml("I'm sorry to hear that", dynamics)
        
        assert '<speak>' in ssml
        assert '</speak>' in ssml
        assert 'rate="slow"' in ssml
        assert 'volume="soft"' in ssml
        assert '<break time="300ms"/>' in ssml
        # Apostrophe will be escaped
        assert "sorry to hear that" in ssml
    
    def test_generate_ssml_with_excited_loud_very_fast(self, generator):
        """Test SSML generation for excited, loud, very fast speech."""
        dynamics = EmotionDynamics(
            emotion="excited",
            intensity=0.9,
            rate_wpm=220,
            volume_level="loud"
        )
        
        ssml = generator.generate_ssml("Amazing news!", dynamics)
        
        assert '<speak>' in ssml
        assert '</speak>' in ssml
        assert 'rate="x-fast"' in ssml
        assert 'volume="loud"' in ssml
        assert '<emphasis level="strong">Amazing news!</emphasis>' in ssml
    
    def test_generate_ssml_escapes_special_characters(self, generator):
        """Test SSML generation escapes XML special characters."""
        dynamics = EmotionDynamics(
            emotion="neutral",
            intensity=0.5,
            rate_wpm=150,
            volume_level="normal"
        )
        
        ssml = generator.generate_ssml("Tom & Jerry: 5 < 10", dynamics)
        
        assert '&amp;' in ssml
        assert '&lt;' in ssml
        assert 'Tom & Jerry' not in ssml  # Should be escaped
    
    def test_generate_ssml_with_whisper_volume(self, generator):
        """Test SSML generation with whisper volume."""
        dynamics = EmotionDynamics(
            emotion="neutral",
            intensity=0.3,
            rate_wpm=120,
            volume_level="whisper"
        )
        
        ssml = generator.generate_ssml("Secret message", dynamics)
        
        assert 'volume="x-soft"' in ssml
    
    def test_generate_ssml_structure_is_valid(self, generator):
        """Test SSML generation produces valid structure."""
        dynamics = EmotionDynamics(
            emotion="neutral",
            intensity=0.5,
            rate_wpm=150,
            volume_level="normal"
        )
        
        ssml = generator.generate_ssml("Test message", dynamics)
        
        # Check proper nesting
        assert ssml.startswith('<speak>')
        assert ssml.endswith('</speak>')
        assert '<prosody rate=' in ssml
        assert '<prosody volume=' in ssml
        assert ssml.count('<prosody') == 2
        assert ssml.count('</prosody>') == 2
    
    def test_generate_ssml_with_multiline_text(self, generator):
        """Test SSML generation handles multiline text."""
        dynamics = EmotionDynamics(
            emotion="neutral",
            intensity=0.5,
            rate_wpm=150,
            volume_level="normal"
        )
        
        text = "Line one\nLine two\nLine three"
        ssml = generator.generate_ssml(text, dynamics)
        
        assert 'Line one' in ssml
        assert 'Line two' in ssml
        assert 'Line three' in ssml
    
    def test_generate_ssml_with_empty_text(self, generator):
        """Test SSML generation handles empty text."""
        dynamics = EmotionDynamics(
            emotion="neutral",
            intensity=0.5,
            rate_wpm=150,
            volume_level="normal"
        )
        
        ssml = generator.generate_ssml("", dynamics)
        
        assert '<speak>' in ssml
        assert '</speak>' in ssml
        # Should still have prosody tags even with empty text
        assert '<prosody' in ssml
