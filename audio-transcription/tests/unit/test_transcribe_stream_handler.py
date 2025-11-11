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

