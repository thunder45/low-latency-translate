"""
Unit tests for emotion detection integration in audio processor.

Tests emotion extraction, caching, error handling, and integration
with TranscribeStreamHandler.
"""

import pytest
import numpy as np
import sys
import os
from unittest.mock import Mock, patch, AsyncMock

# Add lambda directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda/audio_processor'))
import handler

from emotion_dynamics.models.audio_dynamics import AudioDynamics
from emotion_dynamics.models.volume_result import VolumeResult
from emotion_dynamics.models.rate_result import RateResult


@pytest.fixture
def mock_emotion_orchestrator():
    """Create mock emotion orchestrator."""
    orchestrator = Mock()
    
    # Mock detect_audio_dynamics to return test dynamics
    volume_result = VolumeResult(
        level='medium',
        db_value=-15.0,
        timestamp=None
    )
    rate_result = RateResult(
        classification='medium',
        wpm=145.0,
        onset_count=10,
        timestamp=None
    )
    dynamics = AudioDynamics(
        volume=volume_result,
        rate=rate_result,
        correlation_id='test-session-123'
    )
    
    orchestrator.detect_audio_dynamics.return_value = (dynamics, 30, 40, 70)
    
    return orchestrator


@pytest.fixture
def valid_audio_data():
    """Create valid PCM audio data."""
    # Generate 100ms of audio at 16kHz (1600 samples)
    sample_rate = 16000
    duration_ms = 100
    num_samples = int(sample_rate * duration_ms / 1000)
    
    # Generate sine wave
    frequency = 440  # A4 note
    t = np.linspace(0, duration_ms / 1000, num_samples)
    audio_array = np.sin(2 * np.pi * frequency * t) * 16384  # Scale to 16-bit range
    audio_array = audio_array.astype(np.int16)
    
    return audio_array.tobytes()


@pytest.mark.asyncio
async def test_process_audio_chunk_with_emotion_success(mock_emotion_orchestrator, valid_audio_data):
    """Test successful emotion extraction from audio chunk."""
    # Setup
    handler.emotion_orchestrator = mock_emotion_orchestrator
    handler.emotion_cache = {}
    session_id = 'test-session-123'
    
    # Execute
    emotion_data = await handler.process_audio_chunk_with_emotion(
        session_id=session_id,
        audio_bytes=valid_audio_data,
        sample_rate=16000
    )
    
    # Verify
    assert emotion_data is not None
    assert 'volume' in emotion_data
    assert 'rate' in emotion_data
    assert 'energy' in emotion_data
    assert 'timestamp' in emotion_data
    
    # Check values are in expected ranges
    assert 0.0 <= emotion_data['volume'] <= 1.0
    assert 0.5 <= emotion_data['rate'] <= 2.0
    assert 0.0 <= emotion_data['energy'] <= 1.0
    
    # Check metadata
    assert emotion_data['volume_level'] == 'medium'
    assert emotion_data['rate_classification'] == 'medium'
    assert emotion_data['volume_db'] == -15.0
    assert emotion_data['rate_wpm'] == 145.0
    
    # Verify cached
    assert session_id in handler.emotion_cache
    assert handler.emotion_cache[session_id] == emotion_data


@pytest.mark.asyncio
async def test_process_audio_chunk_with_emotion_disabled():
    """Test emotion extraction when orchestrator is disabled."""
    # Setup
    handler.emotion_orchestrator = None
    handler.emotion_cache = {}
    session_id = 'test-session-123'
    audio_bytes = b'\x00\x01' * 100
    
    # Execute
    emotion_data = await handler.process_audio_chunk_with_emotion(
        session_id=session_id,
        audio_bytes=audio_bytes
    )
    
    # Verify
    assert emotion_data is None
    assert session_id not in handler.emotion_cache


@pytest.mark.asyncio
async def test_process_audio_chunk_with_emotion_error_handling(valid_audio_data):
    """Test error handling when emotion extraction fails."""
    # Setup
    mock_orchestrator = Mock()
    mock_orchestrator.detect_audio_dynamics.side_effect = Exception("Extraction failed")
    
    handler.emotion_orchestrator = mock_orchestrator
    handler.emotion_cache = {}
    session_id = 'test-session-123'
    
    with patch.object(handler, 'cloudwatch') as mock_cloudwatch:
        # Execute
        emotion_data = await handler.process_audio_chunk_with_emotion(
            session_id=session_id,
            audio_bytes=valid_audio_data
        )
        
        # Verify default values returned
        assert emotion_data is not None
        assert emotion_data['volume'] == 0.5
        assert emotion_data['rate'] == 1.0
        assert emotion_data['energy'] == 0.5
        assert emotion_data['volume_level'] == 'medium'
        assert emotion_data['rate_classification'] == 'medium'
        
        # Verify cached with defaults
        assert session_id in handler.emotion_cache
        assert handler.emotion_cache[session_id] == emotion_data
        
        # Verify error metric emitted
        mock_cloudwatch.put_metric_data.assert_called()
        call_args = mock_cloudwatch.put_metric_data.call_args
        assert call_args[1]['Namespace'] == 'AudioTranscription/EmotionDetection'
        metric_data = call_args[1]['MetricData']
        assert any(m['MetricName'] == 'EmotionExtractionErrors' for m in metric_data)


@pytest.mark.asyncio
async def test_emotion_caching_by_session_id(mock_emotion_orchestrator, valid_audio_data):
    """Test emotion data is cached correctly by session_id."""
    # Setup
    handler.emotion_orchestrator = mock_emotion_orchestrator
    handler.emotion_cache = {}
    
    session_id_1 = 'session-1'
    session_id_2 = 'session-2'
    
    # Execute - process audio for two different sessions
    emotion_data_1 = await handler.process_audio_chunk_with_emotion(
        session_id=session_id_1,
        audio_bytes=valid_audio_data
    )
    
    emotion_data_2 = await handler.process_audio_chunk_with_emotion(
        session_id=session_id_2,
        audio_bytes=valid_audio_data
    )
    
    # Verify both sessions cached separately
    assert session_id_1 in handler.emotion_cache
    assert session_id_2 in handler.emotion_cache
    assert handler.emotion_cache[session_id_1] == emotion_data_1
    assert handler.emotion_cache[session_id_2] == emotion_data_2


@pytest.mark.asyncio
async def test_emotion_data_included_in_translation_payload():
    """Test emotion data is included when forwarding to Translation Pipeline."""
    # Setup
    from shared.services.transcribe_stream_handler import TranscribeStreamHandler
    from shared.services.partial_result_processor import PartialResultProcessor
    from shared.models.configuration import PartialResultConfig
    
    config = PartialResultConfig()
    processor = PartialResultProcessor(
        config=config,
        session_id='test-session',
        source_language='en'
    )
    
    stream_handler = TranscribeStreamHandler(
        output_stream=None,
        processor=processor,
        session_id='test-session',
        source_language='en'
    )
    
    # Mock translation pipeline
    mock_translation = Mock()
    mock_translation.process = Mock(return_value=True)
    stream_handler.translation_pipeline = mock_translation
    
    # Set up emotion cache
    emotion_cache = {
        'test-session': {
            'volume': 0.7,
            'rate': 1.2,
            'energy': 0.8
        }
    }
    stream_handler.emotion_cache = emotion_cache
    
    # Execute
    await stream_handler._forward_to_translation(
        text='Hello world',
        is_partial=False,
        stability_score=1.0,
        timestamp=1234567890.0
    )
    
    # Verify translation pipeline called with emotion data
    mock_translation.process.assert_called_once()
    call_kwargs = mock_translation.process.call_args[1]
    
    assert 'emotion_dynamics' in call_kwargs
    emotion_dynamics = call_kwargs['emotion_dynamics']
    assert emotion_dynamics['volume'] == 0.7
    assert emotion_dynamics['rate'] == 1.2
    assert emotion_dynamics['energy'] == 0.8


@pytest.mark.asyncio
async def test_emotion_cache_cleared_on_session_end():
    """Test emotion cache is cleared when session ends."""
    # Setup
    handler.emotion_cache = {
        'session-1': {'volume': 0.5, 'rate': 1.0, 'energy': 0.5},
        'session-2': {'volume': 0.7, 'rate': 1.2, 'energy': 0.8}
    }
    
    # Mock active stream
    mock_client = Mock()
    mock_manager = Mock()
    mock_manager.end_stream = AsyncMock()
    mock_handler = Mock()
    mock_buffer = Mock()
    mock_buffer.clear = Mock()
    
    handler.active_streams = {
        'session-1': (mock_client, mock_manager, mock_handler, mock_buffer, 1234567890.0, True)
    }
    
    # Execute
    await handler._close_stream_async('session-1')
    
    # Verify emotion cache cleared for session-1 but not session-2
    assert 'session-1' not in handler.emotion_cache
    assert 'session-2' in handler.emotion_cache


@pytest.mark.asyncio
async def test_volume_level_mapping(mock_emotion_orchestrator, valid_audio_data):
    """Test volume level is correctly mapped to 0.0-1.0 scale."""
    # Setup
    handler.emotion_orchestrator = mock_emotion_orchestrator
    handler.emotion_cache = {}
    
    # Test different volume levels
    volume_levels = ['whisper', 'soft', 'medium', 'loud']
    expected_values = [0.2, 0.4, 0.6, 1.0]
    
    for level, expected in zip(volume_levels, expected_values):
        # Update mock to return specific volume level
        volume_result = VolumeResult(level=level, db_value=-20.0, timestamp=None)
        rate_result = RateResult(classification='medium', wpm=145.0, onset_count=10, timestamp=None)
        dynamics = AudioDynamics(volume=volume_result, rate=rate_result, correlation_id='test')
        mock_emotion_orchestrator.detect_audio_dynamics.return_value = (dynamics, 30, 40, 70)
        
        # Execute
        emotion_data = await handler.process_audio_chunk_with_emotion(
            session_id=f'test-{level}',
            audio_bytes=valid_audio_data
        )
        
        # Verify
        assert emotion_data['volume'] == expected
        assert emotion_data['volume_level'] == level


@pytest.mark.asyncio
async def test_rate_classification_mapping(mock_emotion_orchestrator, valid_audio_data):
    """Test rate classification is correctly mapped to speaking rate multiplier."""
    # Setup
    handler.emotion_orchestrator = mock_emotion_orchestrator
    handler.emotion_cache = {}
    
    # Test different rate classifications
    rate_classifications = ['very_slow', 'slow', 'medium', 'fast', 'very_fast']
    expected_values = [0.7, 0.85, 1.0, 1.15, 1.3]
    
    for classification, expected in zip(rate_classifications, expected_values):
        # Update mock to return specific rate classification
        volume_result = VolumeResult(level='medium', db_value=-15.0, timestamp=None)
        rate_result = RateResult(classification=classification, wpm=145.0, onset_count=10, timestamp=None)
        dynamics = AudioDynamics(volume=volume_result, rate=rate_result, correlation_id='test')
        mock_emotion_orchestrator.detect_audio_dynamics.return_value = (dynamics, 30, 40, 70)
        
        # Execute
        emotion_data = await handler.process_audio_chunk_with_emotion(
            session_id=f'test-{classification}',
            audio_bytes=valid_audio_data
        )
        
        # Verify
        assert emotion_data['rate'] == expected
        assert emotion_data['rate_classification'] == classification


@pytest.mark.asyncio
async def test_cloudwatch_metrics_emitted_on_success(mock_emotion_orchestrator, valid_audio_data):
    """Test CloudWatch metrics are emitted on successful emotion extraction."""
    # Setup
    handler.emotion_orchestrator = mock_emotion_orchestrator
    handler.emotion_cache = {}
    session_id = 'test-session'
    
    with patch.object(handler, 'cloudwatch') as mock_cloudwatch:
        # Execute
        await handler.process_audio_chunk_with_emotion(
            session_id=session_id,
            audio_bytes=valid_audio_data
        )
        
        # Verify metrics emitted
        mock_cloudwatch.put_metric_data.assert_called()
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        assert call_args[1]['Namespace'] == 'AudioTranscription/EmotionDetection'
        metric_data = call_args[1]['MetricData']
        
        # Check for expected metrics
        metric_names = [m['MetricName'] for m in metric_data]
        assert 'EmotionExtractionLatency' in metric_names
        assert 'EmotionCacheSize' in metric_names
        
        # Verify latency metric has correct dimensions
        latency_metric = next(m for m in metric_data if m['MetricName'] == 'EmotionExtractionLatency')
        assert latency_metric['Unit'] == 'Milliseconds'
        assert latency_metric['Dimensions'][0]['Name'] == 'SessionId'
        assert latency_metric['Dimensions'][0]['Value'] == session_id
