"""
Data models for emotion dynamics detection and SSML generation.

This module provides dataclasses for representing audio dynamics,
processing options, and results throughout the pipeline.
"""

from .volume_result import VolumeResult
from .rate_result import RateResult
from .audio_dynamics import AudioDynamics
from .processing_options import ProcessingOptions
from .processing_result import ProcessingResult

__all__ = [
    'VolumeResult',
    'RateResult',
    'AudioDynamics',
    'ProcessingOptions',
    'ProcessingResult',
]
