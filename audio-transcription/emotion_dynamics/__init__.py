"""
Emotion Dynamics Detection & SSML Generation Module.

This module provides audio dynamics extraction (volume, speaking rate) and
SSML generation for preserving speaker vocal characteristics in translated speech.
"""

from .orchestrator import AudioDynamicsOrchestrator
from .detectors.volume_detector import VolumeDetector
from .detectors.speaking_rate_detector import SpeakingRateDetector
from .generators.ssml_generator import SSMLGenerator
from .clients.polly_client import PollyClient

__version__ = "1.0.0"

__all__ = [
    'AudioDynamicsOrchestrator',
    'VolumeDetector',
    'SpeakingRateDetector',
    'SSMLGenerator',
    'PollyClient',
]
