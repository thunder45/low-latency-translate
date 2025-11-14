"""
Unit tests for Parallel Translation Service.

Tests translation orchestration, cache integration, error handling,
and timeout handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
import asyncio

from shared.services.parallel_translation_service import ParallelTranslationService
from shared.services.translation_cache_manager import TranslationCacheManager


class TestParallelTranslationService:
    """Test suite for Parallel Translation Service."""
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Create mock cache manager."""
        return Mock(spec=TranslationCacheManager)
    
    @pytest.fixture
    def mock_translate_client(self):
        """Create mock AWS Translate client."""
        return Mock()
    
    @pytest.fixture
    def service(self, mock_cache_manager, mock_translate_client):
        """Create service instance with mocks."""
        return ParallelTranslationService(
            cache_manager=mock_cache_manager,
            translate_client=mock_translate_client,
            timeout_seconds=2
        )
    
    def test_translate_to_languages_with_cache_hits(
        self,
        service,
        mock_cache_manager
    ):
        """Test translation with all cache hits."""
        # Arrange
        source_lang = 'en'
        text = 'Hello world'
        target_languages = ['es', 'fr', 'de']
        
        # Mock cache returns translations for all languages
        mock_cache_manager.get_cached_translation.side_effect = [
            'Hola mundo',  # Spanish
            'Bonjour le monde',  # French
            'Hallo Welt'  # German
        ]
        
        # Act
        results = service.translate_to_languages(
            source_lang,
            text,
            target_languages
        )
        
        # Assert
        assert len(results) == 3
        assert results['es'] == 'Hola mundo'
        assert results['fr'] == 'Bonjour le monde'
        assert results['de'] == 'Hallo Welt'
        
        # Verify cache was checked for all languages
        assert mock_cache_manager.get_cached_translation.call_count == 3
        
        # Verify no API calls were made (all cache hits)
        assert mock_cache_manager.cache_translation.call_count == 0
    
    def test_translate_to_languages_with_cache_misses(
        self,
        service,
        mock_cache_manager,
        mock_translate_client
    ):
        """Test translation with cache misses and API calls."""
        # Arrange
        source_lang = 'en'
        text = 'Hello world'
        target_languages = ['es', 'fr']
        
        # Mock cache returns None (cache miss)
        mock_cache_manager.get_cached_translation.return_value = None
        
        # Mock AWS Translate responses
        mock_translate_client.translate_text.side_effect = [
            {'TranslatedText': 'Hola mundo'},
            {'TranslatedText': 'Bonjour le monde'}
        ]
        
        # Act
        results = service.translate_to_languages(
            source_lang,
            text,
            target_languages
        )
        
        # Assert
        assert len(results) == 2
        assert results['es'] == 'Hola mundo'
        assert results['fr'] == 'Bonjour le monde'
        
        # Verify cache was checked
        assert mock_cache_manager.get_cached_translation.call_count == 2
        
        # Verify API was called
        assert mock_translate_client.translate_text.call_count == 2
        
        # Verify translations were cached
        assert mock_cache_manager.cache_translation.call_count == 2
        mock_cache_manager.cache_translation.assert_any_call(
            'en', 'es', 'Hello world', 'Hola mundo'
        )
        mock_cache_manager.cache_translation.assert_any_call(
            'en', 'fr', 'Hello world', 'Bonjour le monde'
        )
    
    def test_translate_to_languages_with_mixed_cache_results(
        self,
        service,
        mock_cache_manager,
        mock_translate_client
    ):
        """Test translation with some cache hits and some misses."""
        # Arrange
        source_lang = 'en'
        text = 'Hello world'
        target_languages = ['es', 'fr', 'de']
        
        # Mock cache: hit for Spanish, miss for French and German
        mock_cache_manager.get_cached_translation.side_effect = [
            'Hola mundo',  # Spanish - cache hit
            None,  # French - cache miss
            None   # German - cache miss
        ]
        
        # Mock AWS Translate for cache misses
        mock_translate_client.translate_text.side_effect = [
            {'TranslatedText': 'Bonjour le monde'},
            {'TranslatedText': 'Hallo Welt'}
        ]
        
        # Act
        results = service.translate_to_languages(
            source_lang,
            text,
            target_languages
        )
        
        # Assert
        assert len(results) == 3
        assert results['es'] == 'Hola mundo'
        assert results['fr'] == 'Bonjour le monde'
        assert results['de'] == 'Hallo Welt'
        
        # Verify cache was checked for all languages
        assert mock_cache_manager.get_cached_translation.call_count == 3
        
        # Verify API was called only for cache misses
        assert mock_translate_client.translate_text.call_count == 2
        
        # Verify only cache misses were stored
        assert mock_cache_manager.cache_translation.call_count == 2
    
    def test_translate_to_languages_handles_translate_error(
        self,
        service,
        mock_cache_manager,
        mock_translate_client
    ):
        """Test error handling for AWS Translate failures."""
        # Arrange
        source_lang = 'en'
        text = 'Hello world'
        target_languages = ['es', 'fr', 'de']
        
        # Mock cache miss for all
        mock_cache_manager.get_cached_translation.return_value = None
        
        # Mock AWS Translate: success for Spanish, error for French, success for German
        mock_translate_client.translate_text.side_effect = [
            {'TranslatedText': 'Hola mundo'},
            ClientError(
                {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
                'TranslateText'
            ),
            {'TranslatedText': 'Hallo Welt'}
        ]
        
        # Act
        results = service.translate_to_languages(
            source_lang,
            text,
            target_languages,
            session_id='test-session-123'
        )
        
        # Assert - French should be omitted due to error
        assert len(results) == 2
        assert results['es'] == 'Hola mundo'
        assert results['de'] == 'Hallo Welt'
        assert 'fr' not in results
        
        # Verify only successful translations were cached
        assert mock_cache_manager.cache_translation.call_count == 2
    
    def test_translate_to_languages_handles_timeout(
        self,
        service,
        mock_cache_manager,
        mock_translate_client
    ):
        """Test timeout handling for slow translations."""
        # Arrange
        source_lang = 'en'
        text = 'Hello world'
        target_languages = ['es', 'fr']
        
        # Mock cache miss
        mock_cache_manager.get_cached_translation.return_value = None
        
        # Mock AWS Translate: success for Spanish, timeout for French
        def translate_side_effect(*args, **kwargs):
            target = kwargs.get('TargetLanguageCode')
            if target == 'es':
                return {'TranslatedText': 'Hola mundo'}
            elif target == 'fr':
                # Simulate slow response that will timeout
                import time
                time.sleep(3)  # Longer than 2-second timeout
                return {'TranslatedText': 'Bonjour le monde'}
        
        mock_translate_client.translate_text.side_effect = translate_side_effect
        
        # Act
        results = service.translate_to_languages(
            source_lang,
            text,
            target_languages,
            session_id='test-session-123'
        )
        
        # Assert - French should be omitted due to timeout
        assert len(results) == 1
        assert results['es'] == 'Hola mundo'
        assert 'fr' not in results
        
        # Verify only successful translation was cached
        assert mock_cache_manager.cache_translation.call_count == 1
    
    def test_translate_to_languages_with_empty_target_list(
        self,
        service,
        mock_cache_manager
    ):
        """Test translation with empty target language list."""
        # Arrange
        source_lang = 'en'
        text = 'Hello world'
        target_languages = []
        
        # Act
        results = service.translate_to_languages(
            source_lang,
            text,
            target_languages
        )
        
        # Assert
        assert len(results) == 0
        assert mock_cache_manager.get_cached_translation.call_count == 0
    
    def test_translate_to_languages_with_session_context(
        self,
        service,
        mock_cache_manager,
        mock_translate_client,
        capsys
    ):
        """Test that session context is included in error logs."""
        # Arrange
        source_lang = 'en'
        text = 'Hello world'
        target_languages = ['es']
        session_id = 'golden-eagle-427'
        
        # Mock cache miss
        mock_cache_manager.get_cached_translation.return_value = None
        
        # Mock AWS Translate error
        mock_translate_client.translate_text.side_effect = ClientError(
            {'Error': {'Code': 'InvalidRequestException', 'Message': 'Invalid'}},
            'TranslateText'
        )
        
        # Act
        results = service.translate_to_languages(
            source_lang,
            text,
            target_languages,
            session_id=session_id
        )
        
        # Assert
        assert len(results) == 0
        
        # Verify error log includes session context
        captured = capsys.readouterr()
        assert 'session_id=golden-eagle-427' in captured.out
        assert 'source=en' in captured.out
        assert 'target=es' in captured.out
    
    def test_translate_to_languages_parallel_execution(
        self,
        service,
        mock_cache_manager,
        mock_translate_client
    ):
        """Test that translations execute in parallel."""
        # Arrange
        source_lang = 'en'
        text = 'Hello world'
        target_languages = ['es', 'fr', 'de']
        
        # Mock cache miss
        mock_cache_manager.get_cached_translation.return_value = None
        
        # Track call order
        call_order = []
        
        def translate_side_effect(*args, **kwargs):
            target = kwargs.get('TargetLanguageCode')
            call_order.append(target)
            return {'TranslatedText': f'Translation to {target}'}
        
        mock_translate_client.translate_text.side_effect = translate_side_effect
        
        # Act
        results = service.translate_to_languages(
            source_lang,
            text,
            target_languages
        )
        
        # Assert
        assert len(results) == 3
        # All three languages should be called (order may vary due to parallelism)
        assert set(call_order) == {'es', 'fr', 'de'}
    
    def test_translate_to_languages_stores_only_successful_translations(
        self,
        service,
        mock_cache_manager,
        mock_translate_client
    ):
        """Test that only successful translations are cached."""
        # Arrange
        source_lang = 'en'
        text = 'Hello world'
        target_languages = ['es', 'fr', 'de']
        
        # Mock cache miss
        mock_cache_manager.get_cached_translation.return_value = None
        
        # Mock AWS Translate: success, error, success
        mock_translate_client.translate_text.side_effect = [
            {'TranslatedText': 'Hola mundo'},
            ClientError(
                {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service down'}},
                'TranslateText'
            ),
            {'TranslatedText': 'Hallo Welt'}
        ]
        
        # Act
        results = service.translate_to_languages(
            source_lang,
            text,
            target_languages
        )
        
        # Assert
        assert len(results) == 2
        
        # Verify only successful translations were cached
        assert mock_cache_manager.cache_translation.call_count == 2
        
        # Verify the correct translations were cached
        cached_calls = mock_cache_manager.cache_translation.call_args_list
        cached_langs = [call[0][1] for call in cached_calls]
        assert 'es' in cached_langs
        assert 'de' in cached_langs
        assert 'fr' not in cached_langs
    
    def test_translate_single_with_unexpected_error(
        self,
        service,
        mock_cache_manager,
        mock_translate_client,
        capsys
    ):
        """Test handling of unexpected errors during translation."""
        # Arrange
        source_lang = 'en'
        text = 'Hello world'
        target_languages = ['es']
        
        # Mock cache miss
        mock_cache_manager.get_cached_translation.return_value = None
        
        # Mock unexpected error
        mock_translate_client.translate_text.side_effect = ValueError(
            "Unexpected error"
        )
        
        # Act
        results = service.translate_to_languages(
            source_lang,
            text,
            target_languages,
            session_id='test-session'
        )
        
        # Assert
        assert len(results) == 0
        
        # Verify error was logged
        captured = capsys.readouterr()
        assert 'Unexpected translation error' in captured.out
        assert 'ValueError' in captured.out
