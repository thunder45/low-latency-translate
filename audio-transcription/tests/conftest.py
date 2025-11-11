"""
Shared pytest fixtures for audio-transcription tests.
"""

import time
import pytest
from shared.models import (
    PartialResult,
    FinalResult,
    BufferedResult,
    PartialResultConfig
)


@pytest.fixture
def valid_partial_result():
    """Fixture providing a valid partial result."""
    return PartialResult(
        result_id='test-result-123',
        text='hello everyone this is a test',
        stability_score=0.92,
        timestamp=time.time(),
        session_id='test-session-456',
        source_language='en'
    )


@pytest.fixture
def valid_final_result():
    """Fixture providing a valid final result."""
    return FinalResult(
        result_id='test-result-789',
        text='hello everyone this is important',
        timestamp=time.time(),
        session_id='test-session-456',
        source_language='en',
        replaces_result_ids=['test-result-123', 'test-result-124']
    )


@pytest.fixture
def valid_buffered_result():
    """Fixture providing a valid buffered result."""
    now = time.time()
    return BufferedResult(
        result_id='test-result-123',
        text='hello everyone',
        stability_score=0.85,
        timestamp=now,
        added_at=now + 0.1,
        forwarded=False,
        session_id='test-session-456'
    )


@pytest.fixture
def default_config():
    """Fixture providing default configuration."""
    return PartialResultConfig()


@pytest.fixture
def custom_config():
    """Fixture providing custom configuration."""
    return PartialResultConfig(
        enabled=True,
        min_stability_threshold=0.90,
        max_buffer_timeout_seconds=7.0,
        pause_threshold_seconds=3.0,
        orphan_timeout_seconds=20.0,
        max_rate_per_second=10,
        dedup_cache_ttl_seconds=15
    )
