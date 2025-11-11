"""
Unit tests for result buffer.

Tests buffer operations, capacity management, orphan detection,
and timestamp-based ordering.
"""

import time
import pytest
from shared.models import PartialResult
from shared.services import ResultBuffer


class TestResultBuffer:
    """Test suite for ResultBuffer class."""
    
    def test_buffer_initialization(self):
        """Test buffer initialization with default capacity."""
        buffer = ResultBuffer()
        assert buffer.max_capacity_seconds == 10
        assert buffer.words_per_second == 30
        assert buffer.size() == 0
    
    def test_buffer_initialization_custom_capacity(self):
        """Test buffer initialization with custom capacity."""
        buffer = ResultBuffer(max_capacity_seconds=20)
        assert buffer.max_capacity_seconds == 20
        assert buffer.size() == 0
    
    def test_add_partial_result(self):
        """Test adding a partial result to buffer."""
        buffer = ResultBuffer()
        
        result = PartialResult(
            result_id='result-123',
            text='hello world',
            stability_score=0.92,
            timestamp=time.time(),
            session_id='session-456'
        )
        
        buffer.add(result)
        
        assert buffer.size() == 1
        buffered = buffer.get_by_id('result-123')
        assert buffered is not None
        assert buffered.result_id == 'result-123'
        assert buffered.text == 'hello world'
        assert buffered.forwarded is False
    
    def test_add_multiple_results(self):
        """Test adding multiple results to buffer."""
        buffer = ResultBuffer()
        
        for i in range(5):
            result = PartialResult(
                result_id=f'result-{i}',
                text=f'text {i}',
                stability_score=0.9,
                timestamp=time.time() + i,
                session_id='session-456'
            )
            buffer.add(result)
        
        assert buffer.size() == 5
    
    def test_remove_by_id_existing_result(self):
        """Test removing an existing result by ID."""
        buffer = ResultBuffer()
        
        result = PartialResult(
            result_id='result-123',
            text='hello world',
            stability_score=0.92,
            timestamp=time.time()
        )
        
        buffer.add(result)
        assert buffer.size() == 1
        
        removed = buffer.remove_by_id('result-123')
        
        assert removed is not None
        assert removed.result_id == 'result-123'
        assert buffer.size() == 0
    
    def test_remove_by_id_nonexistent_result(self):
        """Test removing a nonexistent result returns None."""
        buffer = ResultBuffer()
        
        removed = buffer.remove_by_id('nonexistent')
        
        assert removed is None
        assert buffer.size() == 0
    
    def test_get_all_returns_all_results(self):
        """Test get_all() returns all buffered results."""
        buffer = ResultBuffer()
        
        for i in range(3):
            result = PartialResult(
                result_id=f'result-{i}',
                text=f'text {i}',
                stability_score=0.9,
                timestamp=time.time()
            )
            buffer.add(result)
        
        all_results = buffer.get_all()
        
        assert len(all_results) == 3
        result_ids = {r.result_id for r in all_results}
        assert result_ids == {'result-0', 'result-1', 'result-2'}
    
    def test_get_by_id_existing_result(self):
        """Test getting an existing result by ID."""
        buffer = ResultBuffer()
        
        result = PartialResult(
            result_id='result-123',
            text='hello world',
            stability_score=0.92,
            timestamp=time.time()
        )
        
        buffer.add(result)
        
        retrieved = buffer.get_by_id('result-123')
        
        assert retrieved is not None
        assert retrieved.result_id == 'result-123'
        assert buffer.size() == 1  # Not removed
    
    def test_get_by_id_nonexistent_result(self):
        """Test getting a nonexistent result returns None."""
        buffer = ResultBuffer()
        
        retrieved = buffer.get_by_id('nonexistent')
        
        assert retrieved is None
    
    def test_mark_as_forwarded(self):
        """Test marking a result as forwarded."""
        buffer = ResultBuffer()
        
        result = PartialResult(
            result_id='result-123',
            text='hello world',
            stability_score=0.92,
            timestamp=time.time()
        )
        
        buffer.add(result)
        
        # Initially not forwarded
        buffered = buffer.get_by_id('result-123')
        assert buffered.forwarded is False
        
        # Mark as forwarded
        success = buffer.mark_as_forwarded('result-123')
        
        assert success is True
        buffered = buffer.get_by_id('result-123')
        assert buffered.forwarded is True
    
    def test_mark_as_forwarded_nonexistent_result(self):
        """Test marking nonexistent result as forwarded returns False."""
        buffer = ResultBuffer()
        
        success = buffer.mark_as_forwarded('nonexistent')
        
        assert success is False
    
    def test_get_orphaned_results(self):
        """Test getting orphaned results older than timeout."""
        buffer = ResultBuffer()
        
        # Add old result
        old_result = PartialResult(
            result_id='old-result',
            text='old text',
            stability_score=0.9,
            timestamp=time.time() - 20  # 20 seconds ago
        )
        buffer.add(old_result)
        
        # Manually set added_at to simulate age
        buffer.buffer['old-result'].added_at = time.time() - 20
        
        # Add fresh result
        fresh_result = PartialResult(
            result_id='fresh-result',
            text='fresh text',
            stability_score=0.9,
            timestamp=time.time()
        )
        buffer.add(fresh_result)
        
        # Get orphaned results (older than 15 seconds)
        orphaned = buffer.get_orphaned_results(timeout_seconds=15.0)
        
        assert len(orphaned) == 1
        assert orphaned[0].result_id == 'old-result'
    
    def test_get_orphaned_results_none_found(self):
        """Test getting orphaned results when none exist."""
        buffer = ResultBuffer()
        
        # Add fresh result
        result = PartialResult(
            result_id='result-123',
            text='hello world',
            stability_score=0.9,
            timestamp=time.time()
        )
        buffer.add(result)
        
        # Get orphaned results (older than 15 seconds)
        orphaned = buffer.get_orphaned_results(timeout_seconds=15.0)
        
        assert len(orphaned) == 0
    
    def test_sort_by_timestamp(self):
        """Test sorting results by timestamp."""
        buffer = ResultBuffer()
        
        # Add results in random order
        timestamps = [time.time() + i for i in [2, 0, 3, 1]]
        for i, ts in enumerate(timestamps):
            result = PartialResult(
                result_id=f'result-{i}',
                text=f'text {i}',
                stability_score=0.9,
                timestamp=ts
            )
            buffer.add(result)
        
        # Sort by timestamp
        sorted_results = buffer.sort_by_timestamp()
        
        # Verify sorted order (oldest first)
        assert len(sorted_results) == 4
        assert sorted_results[0].result_id == 'result-1'  # timestamp + 0
        assert sorted_results[1].result_id == 'result-3'  # timestamp + 1
        assert sorted_results[2].result_id == 'result-0'  # timestamp + 2
        assert sorted_results[3].result_id == 'result-2'  # timestamp + 3
    
    def test_size_returns_correct_count(self):
        """Test that size() returns correct entry count."""
        buffer = ResultBuffer()
        
        assert buffer.size() == 0
        
        for i in range(5):
            result = PartialResult(
                result_id=f'result-{i}',
                text='text',
                stability_score=0.9,
                timestamp=time.time()
            )
            buffer.add(result)
            assert buffer.size() == i + 1
    
    def test_clear_removes_all_entries(self):
        """Test that clear() removes all entries."""
        buffer = ResultBuffer()
        
        # Add multiple results
        for i in range(5):
            result = PartialResult(
                result_id=f'result-{i}',
                text='text',
                stability_score=0.9,
                timestamp=time.time()
            )
            buffer.add(result)
        
        assert buffer.size() == 5
        
        buffer.clear()
        
        assert buffer.size() == 0
    
    def test_capacity_calculation(self):
        """Test buffer capacity calculation based on word count."""
        buffer = ResultBuffer(max_capacity_seconds=10)
        
        # Add results with known word counts
        # 10 seconds * 30 words/second = 300 words max
        
        # Add 290 words (below capacity)
        for i in range(29):
            result = PartialResult(
                result_id=f'result-{i}',
                text='word ' * 10,  # 10 words
                stability_score=0.9,
                timestamp=time.time()
            )
            buffer.add(result)
        
        # Should not trigger flush yet
        assert buffer.size() == 29
    
    def test_flush_oldest_stable_when_at_capacity(self):
        """Test that oldest stable results are flushed when at capacity."""
        buffer = ResultBuffer(max_capacity_seconds=1)  # Very small capacity
        buffer.words_per_second = 10  # 10 words max
        
        # Add results to exceed capacity
        for i in range(5):
            result = PartialResult(
                result_id=f'result-{i}',
                text='word ' * 3,  # 3 words each
                stability_score=0.9,
                timestamp=time.time() + i
            )
            buffer.add(result)
        
        # After adding 5 results (15 words), should have flushed some
        # Buffer should have fewer than 5 results
        assert buffer.size() < 5
    
    def test_flush_oldest_stable_prefers_high_stability(self):
        """Test that flush prefers results with high stability."""
        buffer = ResultBuffer()
        
        # Add results with different stability scores
        for i in range(10):
            result = PartialResult(
                result_id=f'result-{i}',
                text='text',
                stability_score=0.85 if i < 5 else 0.70,  # First 5 are stable
                timestamp=time.time() + i
            )
            buffer.add(result)
        
        # Manually flush oldest stable
        flushed = buffer._flush_oldest_stable(count=3)
        
        # Should flush the 3 oldest stable results (0, 1, 2)
        assert len(flushed) == 3
        flushed_ids = {r.result_id for r in flushed}
        assert flushed_ids == {'result-0', 'result-1', 'result-2'}
    
    def test_flush_oldest_stable_handles_none_stability(self):
        """Test that flush treats None stability as stable."""
        buffer = ResultBuffer()
        
        # Add results with None stability
        for i in range(5):
            result = PartialResult(
                result_id=f'result-{i}',
                text='text',
                stability_score=None,  # No stability score
                timestamp=time.time() + i
            )
            buffer.add(result)
        
        # Manually flush oldest stable
        flushed = buffer._flush_oldest_stable(count=2)
        
        # Should flush the 2 oldest (0, 1)
        assert len(flushed) == 2
        flushed_ids = {r.result_id for r in flushed}
        assert flushed_ids == {'result-0', 'result-1'}
    
    def test_buffer_handles_out_of_order_timestamps(self):
        """Test that buffer handles results with out-of-order timestamps."""
        buffer = ResultBuffer()
        
        # Add results with out-of-order timestamps
        timestamps = [time.time() + i for i in [3, 1, 4, 0, 2]]
        for i, ts in enumerate(timestamps):
            result = PartialResult(
                result_id=f'result-{i}',
                text=f'text {i}',
                stability_score=0.9,
                timestamp=ts
            )
            buffer.add(result)
        
        # Sort by timestamp
        sorted_results = buffer.sort_by_timestamp()
        
        # Verify correct chronological order
        for i in range(len(sorted_results) - 1):
            assert sorted_results[i].timestamp <= sorted_results[i + 1].timestamp
    
    def test_buffer_preserves_session_id(self):
        """Test that buffer preserves session_id from partial result."""
        buffer = ResultBuffer()
        
        result = PartialResult(
            result_id='result-123',
            text='hello world',
            stability_score=0.92,
            timestamp=time.time(),
            session_id='session-456'
        )
        
        buffer.add(result)
        
        buffered = buffer.get_by_id('result-123')
        assert buffered.session_id == 'session-456'
    
    def test_buffer_tracks_added_at_timestamp(self):
        """Test that buffer tracks when result was added."""
        buffer = ResultBuffer()
        
        before_add = time.time()
        
        result = PartialResult(
            result_id='result-123',
            text='hello world',
            stability_score=0.92,
            timestamp=time.time() - 10  # Original timestamp
        )
        
        buffer.add(result)
        
        after_add = time.time()
        
        buffered = buffer.get_by_id('result-123')
        
        # added_at should be recent, not the original timestamp
        assert before_add <= buffered.added_at <= after_add
        assert buffered.timestamp < buffered.added_at
