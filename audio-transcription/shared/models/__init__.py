"""
Data models for real-time audio transcription with partial results.

This module provides dataclasses for representing transcription results,
configuration, and internal processing state.
"""

from .transcription_results import (
    PartialResult,
    FinalResult,
    BufferedResult,
    ResultMetadata
)
from .configuration import PartialResultConfig
from .cache import CacheEntry

__all__ = [
    'PartialResult',
    'FinalResult',
    'BufferedResult',
    'ResultMetadata',
    'PartialResultConfig',
    'CacheEntry'
]
