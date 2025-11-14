"""Unit tests for Audio Buffer Manager."""

import pytest
from unittest.mock import Mock, patch
from shared.services.audio_buffer_manager import AudioBufferManager


class TestAudioBufferManager:
    """Test suite for AudioBufferManager."""
    
    @pytest.fixture
    def manager(self):
        """Create AudioBufferManager instance."""
        return AudioBufferManager(max_buffer_seconds=10)
    
    @pytest.fixture
    def mock_cloudwatch(self):
        """Create mock CloudWatch client."""
        return Mock()
    
    # Test initialization
    
    def test_init_with_default_values(self):
        """Test initialization with default values."""
        manager = AudioBufferManager()
        
        assert manager.max_buffer_seconds == 10
        assert manager.max_buffer_bytes == 10 * 16000 * 2  # 10s * 16kHz * 2 bytes
        assert manager.buffers == {}
        assert manager.buffer_sizes == {}
        assert manager.overflow_count == 0
    
    def test_init_with_custom_max_buffer(self):
        """Test initialization with custom max buffer."""
        manager = AudioBufferManager(max_buffer_seconds=5)
        
        assert manager.max_buffer_seconds == 5
        assert manager.max_buffer_bytes == 5 * 16000 * 2
    
    def test_init_with_cloudwatch_client(self, mock_cloudwatch):
        """Test initialization with CloudWatch client."""
        manager = AudioBufferManager(cloudwatch_client=mock_cloudwatch)
        
        assert manager.cloudwatch_client == mock_cloudwatch
    
    # Test add_audio
    
    def test_add_audio_to_new_connection(self, manager):
        """Test adding audio to new connection initializes buffer."""
        audio_chunk = b'audio_data_here'
        
        result = manager.add_audio("conn-123", audio_chunk)
        
        assert result is True
        assert "conn-123" in manager.buffers
        assert "conn-123" in manager.buffer_sizes
        assert len(manager.buffers["conn-123"]) == 1
        assert manager.buffer_sizes["conn-123"] == len(audio_chunk)
    
    def test_add_audio_to_existing_connection(self, manager):
        """Test adding audio to existing connection appends to buffer."""
        audio_chunk1 = b'first_chunk'
        audio_chunk2 = b'second_chunk'
        
        manager.add_audio("conn-123", audio_chunk1)
        manager.add_audio("conn-123", audio_chunk2)
        
        assert len(manager.buffers["conn-123"]) == 2
        assert manager.buffer_sizes["conn-123"] == len(audio_chunk1) + len(audio_chunk2)
    
    def test_add_audio_with_session_id(self, manager):
        """Test adding audio includes session ID in logs."""
        audio_chunk = b'audio_data'
        
        result = manager.add_audio("conn-123", audio_chunk, session_id="session-456")
        
        assert result is True
    
    def test_add_audio_triggers_overflow_when_exceeds_capacity(self, manager):
        """Test adding audio triggers overflow when buffer exceeds capacity."""
        # Create audio chunk that's 60% of max buffer
        chunk_size = int(manager.max_buffer_bytes * 0.6)
        large_chunk = b'x' * chunk_size
        
        # Add two chunks (120% of capacity)
        manager.add_audio("conn-123", large_chunk)
        manager.add_audio("conn-123", large_chunk)
        
        # Should have triggered overflow
        assert manager.overflow_count > 0
        # Buffer should not exceed max
        assert manager.buffer_sizes["conn-123"] <= manager.max_buffer_bytes
    
    # Test get_buffered_audio
    
    def test_get_buffered_audio_returns_chunks_in_order(self, manager):
        """Test get_buffered_audio returns chunks in correct order."""
        chunk1 = b'first'
        chunk2 = b'second'
        chunk3 = b'third'
        
        manager.add_audio("conn-123", chunk1)
        manager.add_audio("conn-123", chunk2)
        manager.add_audio("conn-123", chunk3)
        
        buffered = manager.get_buffered_audio("conn-123")
        
        assert len(buffered) == 3
        assert buffered[0] == chunk1
        assert buffered[1] == chunk2
        assert buffered[2] == chunk3
    
    def test_get_buffered_audio_for_nonexistent_connection(self, manager):
        """Test get_buffered_audio returns empty list for nonexistent connection."""
        buffered = manager.get_buffered_audio("nonexistent")
        
        assert buffered == []
    
    # Test clear_buffer
    
    def test_clear_buffer_removes_connection_data(self, manager):
        """Test clear_buffer removes all data for connection."""
        manager.add_audio("conn-123", b'audio_data')
        
        manager.clear_buffer("conn-123")
        
        assert "conn-123" not in manager.buffers
        assert "conn-123" not in manager.buffer_sizes
    
    def test_clear_buffer_for_nonexistent_connection(self, manager):
        """Test clear_buffer handles nonexistent connection gracefully."""
        # Should not raise exception
        manager.clear_buffer("nonexistent")
    
    # Test get_buffer_utilization
    
    def test_get_buffer_utilization_calculates_percentage(self, manager):
        """Test get_buffer_utilization calculates correct percentage."""
        # Add audio that's 50% of max buffer
        chunk_size = int(manager.max_buffer_bytes * 0.5)
        audio_chunk = b'x' * chunk_size
        
        manager.add_audio("conn-123", audio_chunk)
        
        utilization = manager.get_buffer_utilization("conn-123")
        
        assert 49.0 < utilization < 51.0  # Allow for rounding
    
    def test_get_buffer_utilization_for_empty_buffer(self, manager):
        """Test get_buffer_utilization returns 0 for empty buffer."""
        utilization = manager.get_buffer_utilization("nonexistent")
        
        assert utilization == 0.0
    
    def test_get_buffer_utilization_for_full_buffer(self, manager):
        """Test get_buffer_utilization returns 100 for full buffer."""
        # Fill buffer to max
        audio_chunk = b'x' * manager.max_buffer_bytes
        manager.add_audio("conn-123", audio_chunk)
        
        utilization = manager.get_buffer_utilization("conn-123")
        
        assert 99.0 < utilization <= 100.0
    
    # Test get_buffer_duration
    
    def test_get_buffer_duration_calculates_seconds(self, manager):
        """Test get_buffer_duration calculates correct duration."""
        # Add 1 second of audio (16000 samples * 2 bytes = 32000 bytes)
        one_second_bytes = 16000 * 2
        audio_chunk = b'x' * one_second_bytes
        
        manager.add_audio("conn-123", audio_chunk)
        
        duration = manager.get_buffer_duration("conn-123")
        
        assert 0.99 < duration < 1.01  # Allow for rounding
    
    def test_get_buffer_duration_for_empty_buffer(self, manager):
        """Test get_buffer_duration returns 0 for empty buffer."""
        duration = manager.get_buffer_duration("nonexistent")
        
        assert duration == 0.0
    
    # Test overflow handling
    
    def test_handle_overflow_drops_oldest_packets(self, manager):
        """Test overflow handling drops oldest packets first."""
        # Add three chunks
        chunk1 = b'first' * 1000
        chunk2 = b'second' * 1000
        chunk3 = b'third' * 1000
        
        manager.add_audio("conn-123", chunk1)
        manager.add_audio("conn-123", chunk2)
        manager.add_audio("conn-123", chunk3)
        
        # Add large chunk that triggers overflow
        large_chunk = b'x' * manager.max_buffer_bytes
        manager.add_audio("conn-123", large_chunk)
        
        # Oldest chunks should be dropped
        buffered = manager.get_buffered_audio("conn-123")
        
        # Should only have the large chunk (oldest dropped)
        assert len(buffered) == 1
        assert buffered[0] == large_chunk
    
    def test_handle_overflow_maintains_buffer_size_limit(self, manager):
        """Test overflow handling maintains buffer size limit."""
        # Add chunks until overflow
        chunk = b'x' * 10000
        for _ in range(50):
            manager.add_audio("conn-123", chunk)
        
        # Buffer should never exceed max
        assert manager.buffer_sizes["conn-123"] <= manager.max_buffer_bytes
    
    # Test CloudWatch metrics
    
    def test_emit_overflow_metric_with_cloudwatch_client(self, mock_cloudwatch):
        """Test overflow metric emission with CloudWatch client."""
        manager = AudioBufferManager(
            max_buffer_seconds=1,
            cloudwatch_client=mock_cloudwatch
        )
        
        # Trigger overflow
        large_chunk = b'x' * manager.max_buffer_bytes
        manager.add_audio("conn-123", large_chunk)
        manager.add_audio("conn-123", large_chunk)
        
        # Verify metric was emitted
        mock_cloudwatch.put_metric_data.assert_called()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        assert call_args['Namespace'] == 'TranslationPipeline/AudioBuffer'
        assert call_args['MetricData'][0]['MetricName'] == 'BufferOverflow'
    
    def test_emit_overflow_metric_without_cloudwatch_client(self, manager):
        """Test overflow metric emission without CloudWatch client."""
        # Should not raise exception
        large_chunk = b'x' * manager.max_buffer_bytes
        manager.add_audio("conn-123", large_chunk)
        manager.add_audio("conn-123", large_chunk)
    
    def test_emit_utilization_metrics_with_cloudwatch_client(self, mock_cloudwatch):
        """Test utilization metrics emission with CloudWatch client."""
        manager = AudioBufferManager(cloudwatch_client=mock_cloudwatch)
        
        # Add some audio
        manager.add_audio("conn-123", b'x' * 10000)
        manager.add_audio("conn-456", b'x' * 20000)
        
        manager.emit_utilization_metrics(session_id="session-789")
        
        # Verify metrics were emitted
        mock_cloudwatch.put_metric_data.assert_called()
        call_args = mock_cloudwatch.put_metric_data.call_args[1]
        assert call_args['Namespace'] == 'TranslationPipeline/AudioBuffer'
        
        metric_names = [m['MetricName'] for m in call_args['MetricData']]
        assert 'AverageBufferUtilization' in metric_names
        assert 'MaxBufferUtilization' in metric_names
        assert 'ActiveBuffers' in metric_names
    
    def test_emit_utilization_metrics_without_buffers(self, mock_cloudwatch):
        """Test utilization metrics emission with no active buffers."""
        manager = AudioBufferManager(cloudwatch_client=mock_cloudwatch)
        
        manager.emit_utilization_metrics()
        
        # Should not emit metrics when no buffers
        mock_cloudwatch.put_metric_data.assert_not_called()
    
    def test_emit_utilization_metrics_without_cloudwatch_client(self, manager):
        """Test utilization metrics emission without CloudWatch client."""
        manager.add_audio("conn-123", b'x' * 10000)
        
        # Should not raise exception
        manager.emit_utilization_metrics()
    
    # Test edge cases
    
    def test_add_audio_with_zero_length_chunk(self, manager):
        """Test adding zero-length audio chunk."""
        result = manager.add_audio("conn-123", b'')
        
        assert result is True
        assert manager.buffer_sizes["conn-123"] == 0
    
    def test_multiple_connections_independent_buffers(self, manager):
        """Test multiple connections maintain independent buffers."""
        manager.add_audio("conn-1", b'audio1')
        manager.add_audio("conn-2", b'audio2')
        manager.add_audio("conn-3", b'audio3')
        
        assert len(manager.buffers) == 3
        assert manager.get_buffered_audio("conn-1") == [b'audio1']
        assert manager.get_buffered_audio("conn-2") == [b'audio2']
        assert manager.get_buffered_audio("conn-3") == [b'audio3']
    
    def test_buffer_constants_are_correct(self):
        """Test audio format constants are correct."""
        assert AudioBufferManager.SAMPLE_RATE == 16000
        assert AudioBufferManager.BYTES_PER_SAMPLE == 2
        assert AudioBufferManager.BYTES_PER_SECOND == 32000
