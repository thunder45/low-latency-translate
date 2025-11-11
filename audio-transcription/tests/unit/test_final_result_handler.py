"""
Unit tests for FinalResultHandler.

Tests cover:
- Partial result removal from buffer
- Deduplication cache checking
- Discrepancy calculation and logging
- Handling of missing corresponding partials
"""

import time
import pytest
from unittest.mock import Mock, MagicMock, patch
from shared.models import FinalResult, PartialResult, BufferedResult
from shared.services.final_result_handler import FinalResultHandler
from shared.services.result_buffer import ResultBuffer
from shared.services.deduplication_cache import DeduplicationCache
from shared.services.translation_forwarder import TranslationForwarder


class TestFinalResultHandler:
    """Test suite for FinalResultHandler."""
    
    @pytest.fixture
    def result_buffer(self):
        """Create result buffer for testing."""
        return ResultBuffer(max_capacity_seconds=10)
    
    @pytest.fixture
    def dedup_cache(self):
        """Create deduplication cache for testing."""
        return DeduplicationCache(ttl_seconds=10)
    
    @pytest.fixture
    def mock_translation_pipeline(self):
        """Create mock translation pipeline."""
        pipeline = Mock()
        pipeline.process = Mock()
        return pipeline
    
    @pytest.fixture
    def translation_forwarder(self, dedup_cache, mock_translation_pipeline):
        """Create translation forwarder for testing."""
        return TranslationForwarder(dedup_cache, mock_translation_pipeline)
    
    @pytest.fixture
    def handler(self, result_buffer, dedup_cache, translation_forwarder):
        """Create final result handler for testing."""
        return FinalResultHandler(
            result_buffer=result_buffer,
            dedup_cache=dedup_cache,
            translation_forwarder=translation_forwarder,
            discrepancy_threshold=20.0
        )
    
    def test_initialization(self, handler):
        """Test handler initializes correctly."""
        assert handler.result_buffer is not None
        assert handler.dedup_cache is not None
        assert handler.translation_forwarder is not None
        assert handler.discrepancy_threshold == 20.0
    
    def test_process_removes_partial_by_id(self, handler, result_buffer):
        """Test that process removes partial result by explicit ID."""
        # Add partial result to buffer
        partial = PartialResult(
            result_id='partial-123',
            text='hello everyone',
            stability_score=0.9,
            timestamp=time.time(),
            session_id='session-1',
            source_language='en'
        )
        result_buffer.add(partial)
        
        # Create final result that replaces the partial
        final = FinalResult(
            result_id='final-123',
            text='hello everyone',
            timestamp=time.time(),
            session_id='session-1',
            source_language='en',
            replaces_result_ids=['partial-123']
        )
        
        # Process final result
        handler.process(final)
        
        # Verify partial was removed from buffer
        assert result_buffer.get_by_id('partial-123') is None
        assert result_buffer.size() == 0
    
    def test_process_removes_partial_by_timestamp(self, handler, result_buffer):
        """Test that process removes partial result by timestamp range."""
        # Add partial result to buffer
        base_time = time.time()
        partial = PartialResult(
            result_id='partial-456',
            text='this is a test',
            stability_score=0.85,
            timestamp=base_time,
            session_id='session-2',
            source_language='en'
        )
        result_buffer.add(partial)
        
        # Create final result 2 seconds later (within 5-second window)
        final = FinalResult(
            result_id='final-456',
            text='this is a test',
            timestamp=base_time + 2.0,
            session_id='session-2',
            source_language='en'
        )
        
        # Process final result
        handler.process(final)
        
        # Verify partial was removed from buffer
        assert result_buffer.get_by_id('partial-456') is None
        assert result_buffer.size() == 0
    
    def test_process_skips_duplicate_from_cache(
        self,
        handler,
        dedup_cache,
        mock_translation_pipeline
    ):
        """Test that process skips final result if already in cache."""
        # Add text to cache
        dedup_cache.add('hello world')
        
        # Create final result with same text
        final = FinalResult(
            result_id='final-789',
            text='Hello World!',  # Different case/punctuation
            timestamp=time.time(),
            session_id='session-3',
            source_language='en'
        )
        
        # Process final result
        handler.process(final)
        
        # Verify translation pipeline was not called
        mock_translation_pipeline.process.assert_not_called()
    
    def test_process_forwards_to_translation(
        self,
        handler,
        mock_translation_pipeline
    ):
        """Test that process forwards final result to translation."""
        # Create final result
        final = FinalResult(
            result_id='final-101',
            text='new unique text',
            timestamp=time.time(),
            session_id='session-4',
            source_language='en'
        )
        
        # Process final result
        handler.process(final)
        
        # Verify translation pipeline was called
        mock_translation_pipeline.process.assert_called_once_with(
            text='new unique text',
            session_id='session-4',
            source_language='en'
        )
    
    def test_calculate_discrepancy_identical_text(self, handler):
        """Test discrepancy calculation with identical text."""
        discrepancy = handler._calculate_discrepancy(
            'hello world',
            'hello world'
        )
        assert discrepancy == 0.0
    
    def test_calculate_discrepancy_different_text(self, handler):
        """Test discrepancy calculation with different text."""
        # "hello" vs "hello world" = 6 character difference
        # max_length = 11
        # discrepancy = (6 / 11) * 100 = 54.5%
        discrepancy = handler._calculate_discrepancy(
            'hello',
            'hello world'
        )
        assert 54.0 <= discrepancy <= 55.0
    
    def test_calculate_discrepancy_minor_changes(self, handler):
        """Test discrepancy calculation with minor changes."""
        # "hello everyone" vs "hello everyone!" = 1 character difference
        # max_length = 15
        # discrepancy = (1 / 15) * 100 = 6.7%
        discrepancy = handler._calculate_discrepancy(
            'hello everyone',
            'hello everyone!'
        )
        assert 6.0 <= discrepancy <= 7.0
    
    def test_calculate_discrepancy_empty_strings(self, handler):
        """Test discrepancy calculation with empty strings."""
        discrepancy = handler._calculate_discrepancy('', '')
        assert discrepancy == 0.0
    
    @patch('shared.services.final_result_handler.logger')
    def test_logs_warning_for_high_discrepancy(
        self,
        mock_logger,
        handler,
        result_buffer
    ):
        """Test that high discrepancy triggers warning log."""
        # Add partial result to buffer and mark as forwarded
        base_time = time.time()
        partial = PartialResult(
            result_id='partial-999',
            text='hello',
            stability_score=0.9,
            timestamp=base_time,
            session_id='session-5',
            source_language='en'
        )
        result_buffer.add(partial)
        result_buffer.mark_as_forwarded('partial-999')
        
        # Create final result with significantly different text
        final = FinalResult(
            result_id='final-999',
            text='hello everyone this is completely different',
            timestamp=base_time + 1.0,
            session_id='session-5',
            source_language='en'
        )
        
        # Process final result
        handler.process(final)
        
        # Verify warning was logged
        warning_calls = [
            call for call in mock_logger.warning.call_args_list
            if 'Significant discrepancy detected' in str(call)
        ]
        assert len(warning_calls) > 0
    
    @patch('shared.services.final_result_handler.logger')
    def test_no_warning_for_low_discrepancy(
        self,
        mock_logger,
        handler,
        result_buffer
    ):
        """Test that low discrepancy does not trigger warning."""
        # Add partial result to buffer and mark as forwarded
        base_time = time.time()
        partial = PartialResult(
            result_id='partial-888',
            text='hello everyone',
            stability_score=0.9,
            timestamp=base_time,
            session_id='session-6',
            source_language='en'
        )
        result_buffer.add(partial)
        result_buffer.mark_as_forwarded('partial-888')
        
        # Create final result with minor difference
        final = FinalResult(
            result_id='final-888',
            text='hello everyone!',
            timestamp=base_time + 1.0,
            session_id='session-6',
            source_language='en'
        )
        
        # Process final result
        handler.process(final)
        
        # Verify warning was not logged
        warning_calls = [
            call for call in mock_logger.warning.call_args_list
            if 'Significant discrepancy detected' in str(call)
        ]
        assert len(warning_calls) == 0
    
    def test_handles_missing_corresponding_partials(
        self,
        handler,
        mock_translation_pipeline
    ):
        """Test that handler works when no corresponding partials exist."""
        # Create final result without any partials in buffer
        final = FinalResult(
            result_id='final-777',
            text='standalone final result',
            timestamp=time.time(),
            session_id='session-7',
            source_language='en'
        )
        
        # Process final result (should not raise exception)
        handler.process(final)
        
        # Verify translation pipeline was called
        mock_translation_pipeline.process.assert_called_once()
    
    def test_removes_multiple_partials_by_timestamp(
        self,
        handler,
        result_buffer
    ):
        """Test that multiple partials within timestamp window are removed."""
        # Add multiple partial results to buffer
        base_time = time.time()
        
        partial1 = PartialResult(
            result_id='partial-1',
            text='hello',
            stability_score=0.8,
            timestamp=base_time,
            session_id='session-8',
            source_language='en'
        )
        result_buffer.add(partial1)
        
        partial2 = PartialResult(
            result_id='partial-2',
            text='hello everyone',
            stability_score=0.85,
            timestamp=base_time + 1.0,
            session_id='session-8',
            source_language='en'
        )
        result_buffer.add(partial2)
        
        partial3 = PartialResult(
            result_id='partial-3',
            text='hello everyone this',
            stability_score=0.9,
            timestamp=base_time + 2.0,
            session_id='session-8',
            source_language='en'
        )
        result_buffer.add(partial3)
        
        # Create final result
        final = FinalResult(
            result_id='final-multi',
            text='hello everyone this is the final',
            timestamp=base_time + 3.0,
            session_id='session-8',
            source_language='en'
        )
        
        # Process final result
        handler.process(final)
        
        # Verify all partials were removed
        assert result_buffer.size() == 0
    
    def test_does_not_remove_partials_outside_timestamp_window(
        self,
        handler,
        result_buffer
    ):
        """Test that partials outside 5-second window are not removed."""
        # Add partial result to buffer
        base_time = time.time()
        partial = PartialResult(
            result_id='partial-old',
            text='old partial',
            stability_score=0.9,
            timestamp=base_time - 10.0,  # 10 seconds before final
            session_id='session-9',
            source_language='en'
        )
        result_buffer.add(partial)
        
        # Create final result
        final = FinalResult(
            result_id='final-new',
            text='new final result',
            timestamp=base_time,
            session_id='session-9',
            source_language='en'
        )
        
        # Process final result
        handler.process(final)
        
        # Verify old partial was not removed (outside 5-second window)
        assert result_buffer.get_by_id('partial-old') is not None
        assert result_buffer.size() == 1
    
    def test_only_checks_discrepancy_for_forwarded_partials(
        self,
        handler,
        result_buffer
    ):
        """Test that discrepancy is only checked for forwarded partials."""
        # Add partial result to buffer but don't mark as forwarded
        base_time = time.time()
        partial = PartialResult(
            result_id='partial-not-forwarded',
            text='hello',
            stability_score=0.9,
            timestamp=base_time,
            session_id='session-10',
            source_language='en'
        )
        result_buffer.add(partial)
        # Note: NOT marking as forwarded
        
        # Create final result with different text
        final = FinalResult(
            result_id='final-different',
            text='completely different text',
            timestamp=base_time + 1.0,
            session_id='session-10',
            source_language='en'
        )
        
        # Process final result (should not log discrepancy warning)
        with patch('shared.services.final_result_handler.logger') as mock_logger:
            handler.process(final)
            
            # Verify no discrepancy warning was logged
            warning_calls = [
                call for call in mock_logger.warning.call_args_list
                if 'Significant discrepancy detected' in str(call)
            ]
            assert len(warning_calls) == 0

