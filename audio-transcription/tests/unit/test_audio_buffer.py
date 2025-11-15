"""
Unit tests for audio buffer.
"""

import pytest
from shared.services.audio_buffer import AudioBuffer, BufferStats


class TestAudioBuffer:
    """Test suite for AudioBuffer."""
    
    def test_buffer_initialization(self):
        """Test buffer initializes with correct parameters."""
        buffer = AudioBuffer(capacity_seconds=5.0, chunk_duration_ms=100)
        
        assert buffer.capacity_seconds == 5.0
        assert buffer.chunk_duration_ms == 100
        assert buffer.capacity_chunks == 50  # 5000ms / 100ms
        assert buffer.size() == 0
    
    def test_add_chunk(self):
        """Test adding chunk to buffer."""
        buffer = AudioBuffer(capacity_seconds=1.0, chunk_duration_ms=100)
        
        audio_bytes = b"test audio"
        success = buffer.add_chunk(audio_bytes, 'session-123')
        
        assert success is True
        assert buffer.size() == 1
    
    def test_add_chunk_until_full(self):
        """Test adding chunks until buffer is full."""
        buffer = AudioBuffer(capacity_seconds=0.5, chunk_duration_ms=100)
        # Capacity: 5 chunks
        
        audio_bytes = b"test audio"
        
        # Add 5 chunks (fill buffer)
        for i in range(5):
            success = buffer.add_chunk(audio_bytes, 'session-123')
            assert success is True
        
        assert buffer.is_full() is True
        assert buffer.size() == 5
    
    def test_add_chunk_overflow(self):
        """Test buffer overflow drops oldest chunk."""
        buffer = AudioBuffer(capacity_seconds=0.5, chunk_duration_ms=100)
        # Capacity: 5 chunks
        
        audio_bytes = b"test audio"
        
        # Fill buffer
        for i in range(5):
            buffer.add_chunk(audio_bytes, 'session-123')
        
        # Add one more (should drop oldest)
        success = buffer.add_chunk(audio_bytes, 'session-123')
        
        assert success is False  # Indicates overflow
        assert buffer.size() == 5  # Still at capacity
        assert buffer.total_dropped == 1
        assert buffer.overflow_count == 1
    
    def test_get_chunk(self):
        """Test getting chunk from buffer (FIFO)."""
        buffer = AudioBuffer()
        
        audio1 = b"chunk 1"
        audio2 = b"chunk 2"
        
        buffer.add_chunk(audio1, 'session-123')
        buffer.add_chunk(audio2, 'session-123')
        
        # Should get first chunk
        chunk = buffer.get_chunk()
        assert chunk == audio1
        
        # Should get second chunk
        chunk = buffer.get_chunk()
        assert chunk == audio2
        
        # Buffer should be empty
        assert buffer.is_empty() is True
    
    def test_get_chunk_empty_buffer(self):
        """Test getting chunk from empty buffer returns None."""
        buffer = AudioBuffer()
        
        chunk = buffer.get_chunk()
        
        assert chunk is None
    
    def test_peek_chunk(self):
        """Test peeking at chunk without removing it."""
        buffer = AudioBuffer()
        
        audio_bytes = b"test audio"
        buffer.add_chunk(audio_bytes, 'session-123')
        
        # Peek should return chunk without removing
        chunk = buffer.peek_chunk()
        assert chunk == audio_bytes
        assert buffer.size() == 1  # Still in buffer
        
        # Peek again should return same chunk
        chunk = buffer.peek_chunk()
        assert chunk == audio_bytes
    
    def test_is_empty(self):
        """Test checking if buffer is empty."""
        buffer = AudioBuffer()
        
        assert buffer.is_empty() is True
        
        buffer.add_chunk(b"test", 'session-123')
        
        assert buffer.is_empty() is False
    
    def test_is_full(self):
        """Test checking if buffer is full."""
        buffer = AudioBuffer(capacity_seconds=0.2, chunk_duration_ms=100)
        # Capacity: 2 chunks
        
        assert buffer.is_full() is False
        
        buffer.add_chunk(b"test1", 'session-123')
        assert buffer.is_full() is False
        
        buffer.add_chunk(b"test2", 'session-123')
        assert buffer.is_full() is True
    
    def test_clear(self):
        """Test clearing buffer."""
        buffer = AudioBuffer()
        
        buffer.add_chunk(b"test1", 'session-123')
        buffer.add_chunk(b"test2", 'session-123')
        
        assert buffer.size() == 2
        
        cleared = buffer.clear()
        
        assert cleared == 2
        assert buffer.size() == 0
        assert buffer.is_empty() is True
    
    def test_get_stats(self):
        """Test getting buffer statistics."""
        buffer = AudioBuffer(capacity_seconds=1.0, chunk_duration_ms=100)
        
        buffer.add_chunk(b"test1", 'session-123')
        buffer.add_chunk(b"test2", 'session-123')
        
        stats = buffer.get_stats()
        
        assert isinstance(stats, BufferStats)
        assert stats.capacity_seconds == 1.0
        assert stats.current_size == 2
        assert stats.total_added == 2
        assert stats.total_dropped == 0
        assert stats.overflow_count == 0
        assert stats.is_full is False
    
    def test_get_stats_with_overflow(self):
        """Test statistics include overflow counts."""
        buffer = AudioBuffer(capacity_seconds=0.2, chunk_duration_ms=100)
        # Capacity: 2 chunks
        
        # Fill and overflow
        for i in range(5):
            buffer.add_chunk(b"test", 'session-123')
        
        stats = buffer.get_stats()
        
        assert stats.total_added == 5
        assert stats.total_dropped == 3
        assert stats.overflow_count == 3
        assert stats.current_size == 2
    
    def test_reset_stats(self):
        """Test resetting statistics."""
        buffer = AudioBuffer()
        
        buffer.add_chunk(b"test", 'session-123')
        
        assert buffer.total_added == 1
        
        buffer.reset_stats()
        
        assert buffer.total_added == 0
        assert buffer.total_dropped == 0
        assert buffer.overflow_count == 0
    
    def test_get_buffer_duration_seconds(self):
        """Test calculating buffer duration."""
        buffer = AudioBuffer(chunk_duration_ms=100)
        
        # Add 5 chunks (500ms)
        for i in range(5):
            buffer.add_chunk(b"test", 'session-123')
        
        duration = buffer.get_buffer_duration_seconds()
        
        assert duration == 0.5  # 500ms = 0.5s
    
    def test_get_capacity_utilization(self):
        """Test calculating capacity utilization."""
        buffer = AudioBuffer(capacity_seconds=1.0, chunk_duration_ms=100)
        # Capacity: 10 chunks
        
        # Add 5 chunks (50% utilization)
        for i in range(5):
            buffer.add_chunk(b"test", 'session-123')
        
        utilization = buffer.get_capacity_utilization()
        
        assert utilization == 50.0
    
    def test_fifo_ordering(self):
        """Test FIFO ordering is maintained."""
        buffer = AudioBuffer()
        
        # Add chunks with identifiable data
        for i in range(5):
            buffer.add_chunk(f"chunk {i}".encode(), 'session-123')
        
        # Retrieve and verify order
        for i in range(5):
            chunk = buffer.get_chunk()
            assert chunk == f"chunk {i}".encode()
