"""
Unit tests for TranslationPipelineOrchestrator.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from shared.services.translation_pipeline_orchestrator import (
    TranslationPipelineOrchestrator,
    EmotionDynamics,
    ProcessingResult
)


@pytest.fixture
def emotion_dynamics():
    """Create sample emotion dynamics."""
    return EmotionDynamics(
        emotion='happy',
        intensity=0.8,
        rate_wpm=150,
        volume_level='normal'
    )


@pytest.fixture
def mock_atomic_counter():
    """Create mock atomic counter."""
    counter = Mock()
    counter.get_listener_count = AsyncMock()
    return counter


@pytest.fixture
def mock_connections_repository():
    """Create mock connections repository."""
    repo = Mock()
    repo.get_unique_target_languages = AsyncMock()
    return repo


@pytest.fixture
def mock_translation_service():
    """Create mock translation service."""
    service = Mock()
    service.translate_to_languages = AsyncMock()
    service.last_cache_hit_rate = 0.5
    return service


@pytest.fixture
def mock_ssml_generator():
    """Create mock SSML generator."""
    generator = Mock()
    generator.generate_ssml = Mock()
    return generator


@pytest.fixture
def mock_synthesis_service():
    """Create mock synthesis service."""
    service = Mock()
    service.synthesize_to_languages = AsyncMock()
    return service


@pytest.fixture
def mock_broadcast_handler():
    """Create mock broadcast handler."""
    handler = Mock()
    handler.broadcast_to_language = AsyncMock()
    return handler


@pytest.fixture
def orchestrator(
    mock_atomic_counter,
    mock_connections_repository,
    mock_translation_service,
    mock_ssml_generator,
    mock_synthesis_service,
    mock_broadcast_handler
):
    """Create TranslationPipelineOrchestrator instance."""
    return TranslationPipelineOrchestrator(
        atomic_counter=mock_atomic_counter,
        connections_repository=mock_connections_repository,
        translation_service=mock_translation_service,
        ssml_generator=mock_ssml_generator,
        synthesis_service=mock_synthesis_service,
        broadcast_handler=mock_broadcast_handler
    )


class TestTranslationPipelineOrchestrator:
    """Test suite for TranslationPipelineOrchestrator."""
    
    @pytest.mark.asyncio
    async def test_process_transcript_with_zero_listeners_skips_processing(
        self, orchestrator, mock_atomic_counter, emotion_dynamics
    ):
        """Test that processing is skipped when no listeners."""
        # Arrange
        mock_atomic_counter.get_listener_count.return_value = 0
        
        # Act
        result = await orchestrator.process_transcript(
            session_id='test-session',
            source_language='en',
            transcript_text='Hello world',
            emotion_dynamics=emotion_dynamics
        )
        
        # Assert
        assert result.success is True
        assert result.listener_count == 0
        assert len(result.languages_processed) == 0
        # Verify no further processing occurred
        mock_atomic_counter.get_listener_count.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_transcript_with_no_target_languages_returns_success(
        self,
        orchestrator,
        mock_atomic_counter,
        mock_connections_repository,
        emotion_dynamics
    ):
        """Test handling when no target languages found."""
        # Arrange
        mock_atomic_counter.get_listener_count.return_value = 5
        mock_connections_repository.get_unique_target_languages.return_value = []
        
        # Act
        result = await orchestrator.process_transcript(
            session_id='test-session',
            source_language='en',
            transcript_text='Hello world',
            emotion_dynamics=emotion_dynamics
        )
        
        # Assert
        assert result.success is True
        assert result.listener_count == 5
        assert len(result.languages_processed) == 0
    
    @pytest.mark.asyncio
    async def test_process_transcript_end_to_end_succeeds(
        self,
        orchestrator,
        mock_atomic_counter,
        mock_connections_repository,
        mock_translation_service,
        mock_ssml_generator,
        mock_synthesis_service,
        mock_broadcast_handler,
        emotion_dynamics
    ):
        """Test successful end-to-end processing."""
        # Arrange
        mock_atomic_counter.get_listener_count.return_value = 10
        mock_connections_repository.get_unique_target_languages.return_value = ['es', 'fr']
        mock_translation_service.translate_to_languages.return_value = {
            'es': 'Hola mundo',
            'fr': 'Bonjour le monde'
        }
        mock_ssml_generator.generate_ssml.side_effect = [
            '<speak>Hola mundo</speak>',
            '<speak>Bonjour le monde</speak>'
        ]
        mock_synthesis_service.synthesize_to_languages.return_value = {
            'es': b'audio_es',
            'fr': b'audio_fr'
        }
        
        # Create mock broadcast results
        from shared.services.broadcast_handler import BroadcastResult
        mock_broadcast_handler.broadcast_to_language.side_effect = [
            BroadcastResult(
                success_count=5,
                failure_count=0,
                stale_connections_removed=0,
                total_duration_ms=100.0,
                language='es'
            ),
            BroadcastResult(
                success_count=5,
                failure_count=0,
                stale_connections_removed=0,
                total_duration_ms=100.0,
                language='fr'
            )
        ]
        
        # Act
        result = await orchestrator.process_transcript(
            session_id='test-session',
            source_language='en',
            transcript_text='Hello world',
            emotion_dynamics=emotion_dynamics
        )
        
        # Assert
        assert result.success is True
        assert result.listener_count == 10
        assert set(result.languages_processed) == {'es', 'fr'}
        assert len(result.languages_failed) == 0
        assert result.broadcast_success_rate == 1.0
        assert result.cache_hit_rate == 0.5
        
        # Verify all services were called
        mock_translation_service.translate_to_languages.assert_called_once()
        assert mock_ssml_generator.generate_ssml.call_count == 2
        mock_synthesis_service.synthesize_to_languages.assert_called_once()
        assert mock_broadcast_handler.broadcast_to_language.call_count == 2
    
    @pytest.mark.asyncio
    async def test_process_transcript_handles_translation_failure(
        self,
        orchestrator,
        mock_atomic_counter,
        mock_connections_repository,
        mock_translation_service,
        emotion_dynamics
    ):
        """Test handling when all translations fail."""
        # Arrange
        mock_atomic_counter.get_listener_count.return_value = 10
        mock_connections_repository.get_unique_target_languages.return_value = ['es', 'fr']
        mock_translation_service.translate_to_languages.return_value = {}
        
        # Act
        result = await orchestrator.process_transcript(
            session_id='test-session',
            source_language='en',
            transcript_text='Hello world',
            emotion_dynamics=emotion_dynamics
        )
        
        # Assert
        assert result.success is False
        assert len(result.languages_processed) == 0
        assert set(result.languages_failed) == {'es', 'fr'}
        assert result.error_message == 'All translations failed'
    
    @pytest.mark.asyncio
    async def test_process_transcript_handles_synthesis_failure(
        self,
        orchestrator,
        mock_atomic_counter,
        mock_connections_repository,
        mock_translation_service,
        mock_ssml_generator,
        mock_synthesis_service,
        emotion_dynamics
    ):
        """Test handling when all synthesis operations fail."""
        # Arrange
        mock_atomic_counter.get_listener_count.return_value = 10
        mock_connections_repository.get_unique_target_languages.return_value = ['es']
        mock_translation_service.translate_to_languages.return_value = {'es': 'Hola'}
        mock_ssml_generator.generate_ssml.return_value = '<speak>Hola</speak>'
        mock_synthesis_service.synthesize_to_languages.return_value = {}
        
        # Act
        result = await orchestrator.process_transcript(
            session_id='test-session',
            source_language='en',
            transcript_text='Hello world',
            emotion_dynamics=emotion_dynamics
        )
        
        # Assert
        assert result.success is False
        assert len(result.languages_processed) == 0
        assert result.error_message == 'All synthesis operations failed'
    
    @pytest.mark.asyncio
    async def test_process_transcript_handles_partial_failures(
        self,
        orchestrator,
        mock_atomic_counter,
        mock_connections_repository,
        mock_translation_service,
        mock_ssml_generator,
        mock_synthesis_service,
        mock_broadcast_handler,
        emotion_dynamics
    ):
        """Test handling when some languages succeed and others fail."""
        # Arrange
        mock_atomic_counter.get_listener_count.return_value = 10
        mock_connections_repository.get_unique_target_languages.return_value = [
            'es', 'fr', 'de'
        ]
        # Only es and fr succeed
        mock_translation_service.translate_to_languages.return_value = {
            'es': 'Hola',
            'fr': 'Bonjour'
        }
        mock_ssml_generator.generate_ssml.side_effect = [
            '<speak>Hola</speak>',
            '<speak>Bonjour</speak>'
        ]
        mock_synthesis_service.synthesize_to_languages.return_value = {
            'es': b'audio_es',
            'fr': b'audio_fr'
        }
        
        from shared.services.broadcast_handler import BroadcastResult
        mock_broadcast_handler.broadcast_to_language.side_effect = [
            BroadcastResult(5, 0, 0, 100.0, 'es'),
            BroadcastResult(5, 0, 0, 100.0, 'fr')
        ]
        
        # Act
        result = await orchestrator.process_transcript(
            session_id='test-session',
            source_language='en',
            transcript_text='Hello world',
            emotion_dynamics=emotion_dynamics
        )
        
        # Assert
        assert result.success is True
        assert set(result.languages_processed) == {'es', 'fr'}
        assert result.languages_failed == ['de']
    
    @pytest.mark.asyncio
    async def test_process_transcript_calculates_broadcast_success_rate(
        self,
        orchestrator,
        mock_atomic_counter,
        mock_connections_repository,
        mock_translation_service,
        mock_ssml_generator,
        mock_synthesis_service,
        mock_broadcast_handler,
        emotion_dynamics
    ):
        """Test broadcast success rate calculation."""
        # Arrange
        mock_atomic_counter.get_listener_count.return_value = 10
        mock_connections_repository.get_unique_target_languages.return_value = ['es']
        mock_translation_service.translate_to_languages.return_value = {'es': 'Hola'}
        mock_ssml_generator.generate_ssml.return_value = '<speak>Hola</speak>'
        mock_synthesis_service.synthesize_to_languages.return_value = {'es': b'audio'}
        
        from shared.services.broadcast_handler import BroadcastResult
        mock_broadcast_handler.broadcast_to_language.return_value = BroadcastResult(
            success_count=8,
            failure_count=2,
            stale_connections_removed=0,
            total_duration_ms=100.0,
            language='es'
        )
        
        # Act
        result = await orchestrator.process_transcript(
            session_id='test-session',
            source_language='en',
            transcript_text='Hello world',
            emotion_dynamics=emotion_dynamics
        )
        
        # Assert
        assert result.broadcast_success_rate == 0.8  # 8/10
    
    @pytest.mark.asyncio
    async def test_process_transcript_handles_unexpected_exception_gracefully(
        self,
        orchestrator,
        mock_atomic_counter,
        mock_connections_repository,
        emotion_dynamics
    ):
        """Test graceful handling of exceptions in helper methods."""
        # Arrange
        mock_atomic_counter.get_listener_count.return_value = 10
        mock_connections_repository.get_unique_target_languages.side_effect = Exception(
            'Unexpected error'
        )
        
        # Act
        result = await orchestrator.process_transcript(
            session_id='test-session',
            source_language='en',
            transcript_text='Hello world',
            emotion_dynamics=emotion_dynamics
        )
        
        # Assert
        # Graceful degradation: returns success with no languages processed
        assert result.success is True
        assert result.listener_count == 10
        assert len(result.languages_processed) == 0
    
    @pytest.mark.asyncio
    async def test_process_transcript_includes_duration_metric(
        self,
        orchestrator,
        mock_atomic_counter,
        emotion_dynamics
    ):
        """Test that processing duration is tracked."""
        # Arrange
        mock_atomic_counter.get_listener_count.return_value = 0
        
        # Act
        result = await orchestrator.process_transcript(
            session_id='test-session',
            source_language='en',
            transcript_text='Hello world',
            emotion_dynamics=emotion_dynamics
        )
        
        # Assert
        assert result.total_duration_ms > 0
        assert isinstance(result.total_duration_ms, float)
