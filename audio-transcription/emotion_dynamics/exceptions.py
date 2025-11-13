"""
Custom exceptions for emotion dynamics detection and SSML generation.

This module defines specific exception types for different failure scenarios
in the audio dynamics detection and speech synthesis pipeline.
"""


class EmotionDynamicsError(Exception):
    """Base exception for emotion dynamics module."""
    pass


class VolumeDetectionError(EmotionDynamicsError):
    """
    Raised when volume detection fails.
    
    This can occur due to:
    - Librosa processing failures
    - Invalid audio data
    - Insufficient audio samples
    """
    pass


class RateDetectionError(EmotionDynamicsError):
    """
    Raised when speaking rate detection fails.
    
    This can occur due to:
    - Librosa onset detection failures
    - Invalid audio data
    - Audio too short for rate analysis
    """
    pass


class SSMLValidationError(EmotionDynamicsError):
    """
    Raised when SSML generation produces invalid markup.
    
    This can occur due to:
    - Invalid prosody attribute values
    - XML structure errors
    - Text content with unescaped special characters
    """
    pass


class SynthesisError(EmotionDynamicsError):
    """
    Raised when speech synthesis fails after fallback attempts.
    
    This can occur due to:
    - Amazon Polly service unavailability
    - Authentication/authorization failures
    - Network connectivity issues
    - Exceeded retry attempts
    """
    pass
