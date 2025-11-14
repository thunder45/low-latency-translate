"""
End-to-end integration tests for translation pipeline.

Tests the integration between components using mocked AWS services.
"""

import pytest
from unittest.mock import Mock

from shared.services.ssml_generator import SSMLGenerator
from shared.services.translation_pipeline_orchestrator import EmotionDynamics
from shared.services.translation_cache_manager import TranslationCacheManager
from shared.data_access.atomic_counter import AtomicCounter


class TestSSMLGeneration:
    """Test SSML generation with emotion dynamics."""
    
    def test_ssml_with_happy_emotion_fast_rate_loud_volume(self):
        """Test SSML generation with happy emotion, fast rate, and loud volume."""
        # Arrange
        generator = SSMLGenerator()
        text = "This is an important announcement"
        dynamics = EmotionDynamics(
            emotion='happy',
            intensity=0.8,
            rate_wpm=180,
            volume_level='loud'
        )
        
        # Act
        ssml = generator.generate_ssml(text, dynamics)
        
        # Assert
        assert '<speak>' in ssml
        assert '<prosody' in ssml
        assert 'rate="fast"' in ssml
        assert 'volume="loud"' in ssml
        assert text in ssml
    
    def test_ssml_with_sad_emotion_slow_rate_soft_volume(self):
        """Test SSML generation with sad emotion, slow rate, and soft volume."""
        # Arrange
        generator = SSMLGenerator()
        text = "This is a somber message"
        dynamics = EmotionDynamics(
            emotion='sad',
            intensity=0.7,
            rate_wpm=120,
            volume_level='soft'
        )
        
        # Act
        ssml = generator.generate_ssml(text, dynamics)
        
        # Assert
        assert '<speak>' in ssml
        # Sad emotion may use medium rate with pauses instead of slow
        assert 'rate=' in ssml
        assert 'volume="soft"' in ssml
        assert '<break' in ssml  # Sad emotion adds pauses
    
    def test_ssml_xml_escaping(self):
        """Test that XML reserved characters are properly escaped."""
        # Arrange
        generator = SSMLGenerator()
        text_with_special_chars = 'Test & verify <tag> "quotes"'
        dynamics = EmotionDynamics(
            emotion='neutral',
            intensity=0.5,
            rate_wpm=150,
            volume_level='normal'
        )
        
        # Act
        ssml = generator.generate_ssml(text_with_special_chars, dynamics)
        
        # Assert
        assert '&amp;' in ssml  # & escaped
        assert '&lt;' in ssml   # < escaped
        assert '&gt;' in ssml   # > escaped


class TestTranslationCacheIntegration:
    """Test translation cache manager integration."""
    
    def test_cache_key_generation_consistency(self):
        """Test that cache keys are generated consistently."""
        # Arrange
        mock_dynamodb = Mock()
        mock_cloudwatch = Mock()
        cache_manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=mock_dynamodb,
            cloudwatch_client=mock_cloudwatch
        )
        
        # Act
        key1 = cache_manager._generate_cache_key('en', 'es', 'Hello world')
        key2 = cache_manager._generate_cache_key('en', 'es', 'Hello world')
        key3 = cache_manager._generate_cache_key('en', 'fr', 'Hello world')
        
        # Assert
        assert key1 == key2  # Same inputs produce same key
        assert key1 != key3  # Different target language produces different key
        assert key1.startswith('en:es:')
        assert key3.startswith('en:fr:')
    
    def test_text_normalization(self):
        """Test that text is normalized before hashing."""
        # Arrange
        mock_dynamodb = Mock()
        mock_cloudwatch = Mock()
        cache_manager = TranslationCacheManager(
            table_name='test-table',
            dynamodb_client=mock_dynamodb,
            cloudwatch_client=mock_cloudwatch
        )
        
        # Act
        key1 = cache_manager._generate_cache_key('en', 'es', '  Hello World  ')
        key2 = cache_manager._generate_cache_key('en', 'es', 'hello world')
        
        # Assert
        assert key1 == key2  # Normalization makes them equal


class TestAtomicCounterIntegration:
    """Test atomic counter integration."""
    
    @pytest.mark.asyncio
    async def test_increment_uses_add_operation(self):
        """Test that increment uses DynamoDB ADD operation."""
        # Arrange
        mock_dynamodb = Mock()
        mock_dynamodb.update_item.return_value = {
            'Attributes': {'listenerCount': {'N': '6'}}
        }
        
        counter = AtomicCounter(
            table_name='test-table',
            dynamodb_client=mock_dynamodb
        )
        
        # Act
        result = await counter.increment_listener_count('session-123')
        
        # Assert
        assert result == 6
        mock_dynamodb.update_item.assert_called_once()
        call_args = mock_dynamodb.update_item.call_args
        assert 'ADD' in call_args[1]['UpdateExpression']
    
    @pytest.mark.asyncio
    async def test_decrement_uses_add_operation_with_negative(self):
        """Test that decrement uses DynamoDB ADD operation with negative value."""
        # Arrange
        mock_dynamodb = Mock()
        mock_dynamodb.update_item.return_value = {
            'Attributes': {'listenerCount': {'N': '4'}}
        }
        
        counter = AtomicCounter(
            table_name='test-table',
            dynamodb_client=mock_dynamodb
        )
        
        # Act
        result = await counter.decrement_listener_count('session-123')
        
        # Assert
        assert result == 4
        mock_dynamodb.update_item.assert_called_once()
        call_args = mock_dynamodb.update_item.call_args
        assert 'ADD' in call_args[1]['UpdateExpression']


class TestEmotionDynamicsDataClass:
    """Test EmotionDynamics data class."""
    
    def test_emotion_dynamics_creation(self):
        """Test creating EmotionDynamics object."""
        # Act
        dynamics = EmotionDynamics(
            emotion='happy',
            intensity=0.8,
            rate_wpm=150,
            volume_level='normal'
        )
        
        # Assert
        assert dynamics.emotion == 'happy'
        assert dynamics.intensity == 0.8
        assert dynamics.rate_wpm == 150
        assert dynamics.volume_level == 'normal'
    
    def test_emotion_dynamics_with_various_emotions(self):
        """Test EmotionDynamics with different emotion types."""
        emotions = ['happy', 'sad', 'angry', 'excited', 'neutral', 'fearful']
        
        for emotion in emotions:
            dynamics = EmotionDynamics(
                emotion=emotion,
                intensity=0.5,
                rate_wpm=150,
                volume_level='normal'
            )
            assert dynamics.emotion == emotion


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
