"""
Audio dynamics detectors module.

Provides volume and speaking rate detection from audio signals.
"""

from emotion_dynamics.detectors.volume_detector import VolumeDetector
from emotion_dynamics.detectors.speaking_rate_detector import SpeakingRateDetector

__all__ = ['VolumeDetector', 'SpeakingRateDetector']
