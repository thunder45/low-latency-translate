"""
Unit tests for TranscribeStreamHandler.

This module tests the async stream handler for AWS Transcribe Streaming API
events, including event parsing, stability score extraction, and routing to
the PartialResultProcessor.
"""

import time
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from shared.services.transcribe_stream_handler import TranscribeStreamHandler
from shared.models.transcription_results import PartialResult, FinalResult


class TestTranscribeStreamHandler:
    """Test suite for TranscribeStreamHandler."""
    
    @pytest.fixture
    def mock_processor(self):
        """Create mock PartialResultProcessor."""
        processor = Mock()
        processor.process_partial = AsyncMock()
        processor.process_final = AsyncMock()
        return processor
    
    @pytest.fixture
    def handler(self, mock_processor):
        """Create TranscribeStreamHandler instance."""
        output_stream = Mock()
        return TranscribeStreamHandler(
            output_stream=output_stream,
            processor=mock_processor,
            session_id='test-session-123',
            source_language='en'
        )
    
    @pytest.mark.asyncio
    async def test_handle_partial_result_with_stability(self, handler, mock_processor):
        """Test handling partial result with stability score."""
        # Create mock transcript event
        event = Mock()
        event.transcript = Mock()
        
        result = Mock()
        result.result_id = 'result-123'
        result.is_partial = True
        
        alternative = Mock()
        alternative.transcript = 'hello everyone'
        
        item = Mock()
        item.stability = 0.92
        alternative.items = [item]
        
        result.alternatives = [alternative]
        event.transcript.results = [result]
        
        # Handle event
        await handler.handle_transcript_event(event)
        
        # Verify process_partial was called
        assert mock_processor.process_partial.called
        call_args = mock_processor.process_partial.call_args[0][0]
        assert isinstance(call_args, PartialResult)
        assert call_args.result_id == 'result-123'
        assert call_args.text == 'hello everyone'
        assert call_args.stability_score == 0.92
        assert call_args.session_id == 'test-session-123'
        assert call_args.source_language == 'en'
    
    @pytest.mark.asyncio
    async def test_handle_partial_result_without_stability(self, handler, mock_processor):
        """Test handling partial result without stability score."""
        event = Mock()
        event.transcript = Mock()
        
        result = Mock()
        result.result_id = 'result-456'
        result.is_partial = True
        
        alternative = Mock()
        alternative.transcript = 'test text'
        alternative.items = []  # No items, no stability
        
        result.alternatives = [alternative]
        event.transcript.results = [result]
        
        await handler.handle_transcript_event(event)
        
        assert mock_processor.process_partial.called
        call_args = mock_processor.process_partial.call_args[0][0]
        assert call_args.stability_score is None
    
    @pytest.mark.asyncio
    async def test_handle_final_result(self, handler, mock_processor):
        """Test handling final result."""
        event = Mock()
        event.transcript = Mock()
        
        result = Mock()
        result.result_id = 'result-789'
        result.is_partial = False
        
        alternative = Mock()
        alternative.transcript = 'final text'
        alternative.items = []
        
        result.alternatives = [alternative]
        event.transcript.results = [result]
        
        await handler.handle_transcript_event(event)
        
        assert mock_processor.process_final.called
        call_args = mock_processor.process_final.call_args[0][0]
        assert isinstance(call_args, FinalResult)
        assert call_args.result_id == 'result-789'
        assert call_args.text == 'final text'
    
    @pytest.mark.asyncio
    async def test_handle_event_missing_transcript(self, handler, mock_processor):
        """Test handling event with missing transcript attribute."""
        event = Mock(spec=[])  # No transcript attribute
        
        await handler.handle_transcript_event(event)
        
        # Should not call processor
        assert not mock_processor.process_partial.called
        assert not mock_processor.process_final.called
    
    @pytest.mark.asyncio
    async def test_handle_event_empty_results(self, handler, mock_processor):
        """Test handling event with empty results."""
        event = Mock()
        event.transcript = Mock()
        event.transcript.results = []
        
        await handler.handle_transcript_event(event)
        
        assert not mock_processor.process_partial.called
        assert not mock_processor.process_final.called
    
    @pytest.mark.asyncio
    async def test_handle_event_missing_result_id(self, handler, mock_processor):
        """Test handling event with missing result_id."""
        event = Mock()
        event.transcript = Mock()
        
        result = Mock(spec=['is_partial', 'alternatives'])
        result.is_partial = True
        
        alternative = Mock()
        alternative.transcript = 'test'
        alternative.items = []
        result.alternatives = [alternative]
        
        event.transcript.results = [result]
        
        await handler.handle_transcript_event(event)
        
        # Should generate result_id and process
        assert mock_processor.process_partial.called
    
    @pytest.mark.asyncio
    async def test_handle_event_empty_text(self, handler, mock_processor):
        """Test handling event with empty transcript text."""
        event = Mock()
        event.transcript = Mock()
        
        result = Mock()
        result.result_id = 'result-empty'
        result.is_partial = True
        
        alternative = Mock()
        alternative.transcript = ''  # Empty text
        alternative.items = []
        result.alternatives = [alternative]
        
        event.transcript.results = [result]
        
        await handler.handle_transcript_event(event)
        
        # Should skip empty text
        assert not mock_processor.process_partial.called
    
    def test_extract_stability_score_with_valid_score(self, handler):
        """Test extracting valid stability score."""
        alternative = Mock()
        item = Mock()
        item.stability = 0.85
        alternative.items = [item]
        
        score = handler._extract_stability_score(alternative)
        assert score == 0.85
    
    def test_extract_stability_score_no_items(self, handler):
        """Test extracting stability when no items."""
        alternative = Mock()
        alternative.items = []
        
        score = handler._extract_stability_score(alternative)
        assert score is None
    
    def test_extract_stability_score_missing_stability(self, handler):
        """Test extracting stability when stability field missing."""
        alternative = Mock()
        item = Mock(spec=[])  # No stability attribute
        alternative.items = [item]
        
        score = handler._extract_stability_score(alternative)
        assert score is None
    
    def test_extract_stability_score_out_of_range(self, handler):
        """Test extracting stability score out of range."""
        alternative = Mock()
        item = Mock()
        item.stability = 1.5  # Out of range
        alternative.items = [item]
        
        score = handler._extract_stability_score(alternative)
        assert score == 1.0  # Clamped to max
    
    def test_extract_stability_score_negative(self, handler):
        """Test extracting negative stability score."""
        alternative = Mock()
        item = Mock()
        item.stability = -0.5  # Negative
        alternative.items = [item]
        
        score = handler._extract_stability_score(alternative)
        assert score == 0.0  # Clamped to min
    
    def test_extract_stability_score_invalid_type(self, handler):
        """Test extracting stability with invalid type."""
        alternative = Mock()
        item = Mock()
        item.stability = 'invalid'  # String instead of float
        alternative.items = [item]
        
        score = handler._extract_stability_score(alternative)
        assert score is None
    
    @pytest.mark.asyncio
    async def test_forward_to_translation_partial(self, handler, mock_processor):
        """Test forwarding partial result to Translation Pipeline."""
        # Setup translation pipeline mock
        mock_pipeline = Mock()
        mock_pipeline.process = Mock(return_value=True)
        handler.translation_pipeline = mock_pipeline
        
        # Forward transcription
        await handler._forward_to_translation(
            text='hello world',
            is_partial=True,
            stability_score=0.92,
            timestamp=time.time()
        )
        
        # Verify Translation Pipeline was called
        assert mock_pipeline.process.called
        call_kwargs = mock_pipeline.process.call_args[1]
        assert call_kwargs['text'] == 'hello world'
        assert call_kwargs['session_id'] == 'test-session-123'
        assert call_kwargs['source_language'] == 'en'
        assert call_kwargs['is_partial'] is True
        assert call_kwargs['stability_score'] == 0.92
    
    @pytest.mark.asyncio
    async def test_forward_to_translation_final(self, handler, mock_processor):
        """Test forwarding final result to Translation Pipeline."""
        mock_pipeline = Mock()
        mock_pipeline.process = Mock(return_value=True)
        handler.translation_pipeline = mock_pipeline
        
        await handler._forward_to_translation(
            text='final text',
            is_partial=False,
            stability_score=1.0,
            timestamp=time.time()
        )
        
        assert mock_pipeline.process.called
        call_kwargs = mock_pipeline.process.call_args[1]
        assert call_kwargs['is_partial'] is False
        assert call_kwargs['stability_score'] == 1.0
    
    @pytest.mark.asyncio
    async def test_forward_to_translation_with_emotion_data(self, handler, mock_processor):
        """Test forwarding with cached emotion data."""
        mock_pipeline = Mock()
        mock_pipeline.process = Mock(return_value=True)
        handler.translation_pipeline = mock_pipeline
        
        # Cache emotion data
        timestamp = time.time()
        emotion_data = {'volume': 0.7, 'rate': 1.2, 'energy': 0.8}
        handler.cache_emotion_data(timestamp, emotion_data)
        
        # Forward transcription
        await handler._forward_to_translation(
            text='test',
            is_partial=True,
            stability_score=0.9,
            timestamp=timestamp
        )
        
        # Verify emotion data was included
        call_kwargs = mock_pipeline.process.call_args[1]
        assert call_kwargs['emotion_dynamics'] == emotion_data
    
    @pytest.mark.asyncio
    async def test_forward_to_translation_without_pipeline(self, handler, mock_processor):
        """Test forwarding when Translation Pipeline not configured."""
        handler.translation_pipeline = None
        
        # Should not raise error
        await handler._forward_to_translation(
            text='test',
            is_partial=True,
            stability_score=0.9,
            timestamp=time.time()
        )
    
    def test_cache_emotion_data(self, handler):
        """Test caching emotion data."""
        timestamp = time.time()
        emotion_data = {'volume': 0.7, 'rate': 1.2, 'energy': 0.8}
        
        handler.cache_emotion_data(timestamp, emotion_data)
        
        assert timestamp in handler.emotion_cache
        assert handler.emotion_cache[timestamp] == emotion_data
    
    def test_cache_emotion_data_cleanup(self, handler):
        """Test emotion cache cleanup of old data."""
        current_time = time.time()
        
        # Add old data (15 seconds ago)
        old_timestamp = current_time - 15.0
        handler.cache_emotion_data(old_timestamp, {'volume': 0.5, 'rate': 1.0, 'energy': 0.5})
        
        # Add recent data
        recent_timestamp = current_time - 5.0
        handler.cache_emotion_data(recent_timestamp, {'volume': 0.7, 'rate': 1.2, 'energy': 0.8})
        
        # Add current data
        handler.cache_emotion_data(current_time, {'volume': 0.8, 'rate': 1.3, 'energy': 0.9})
        
        # Old data should be removed (only keeps last 10 seconds)
        assert old_timestamp not in handler.emotion_cache
        assert recent_timestamp in handler.emotion_cache
        assert current_time in handler.emotion_cache
    
    def test_get_cached_emotion_data(self, handler):
        """Test retrieving cached emotion data."""
        timestamp = time.time()
        emotion_data = {'volume': 0.7, 'rate': 1.2, 'energy': 0.8}
        handler.cache_emotion_data(timestamp, emotion_data)
        
        retrieved = handler._get_cached_emotion_data()
        assert retrieved == emotion_data
    
    def test_get_cached_emotion_data_empty_cache(self, handler):
        """Test retrieving emotion data when cache is empty."""
        retrieved = handler._get_cached_emotion_data()
        
        # Should return default values
        assert retrieved == {'volume': 0.5, 'rate': 1.0, 'energy': 0.5}
    
    def test_get_default_emotion(self, handler):
        """Test getting default emotion values."""
        default = handler._get_default_emotion()
        
        assert default['volume'] == 0.5
        assert default['rate'] == 1.0
        assert default['energy'] == 0.5

