"""
Emotion Dynamics Lambda handler for audio dynamics detection and SSML synthesis.

This module provides the Lambda handler for processing speaker audio to detect
paralinguistic features (volume, speaking rate) and generate SSML-enhanced
translated speech via Amazon Polly.
"""

import json
import logging
import base64
import os
from typing import Dict, Any, Optional

import numpy as np

from emotion_dynamics.orchestrator import AudioDynamicsOrchestrator
from emotion_dynamics.models.processing_options import ProcessingOptions
from emotion_dynamics.exceptions import EmotionDynamicsError
from emotion_dynamics.config.settings import get_settings

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global orchestrator instance (singleton per Lambda container)
# Initialized on cold start and reused across invocations
orchestrator: Optional[AudioDynamicsOrchestrator] = None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for emotion dynamics processing.
    
    This handler processes speaker audio to detect volume and speaking rate,
    generates SSML markup with prosody tags, and synthesizes speech via
    Amazon Polly that preserves the speaker's vocal dynamics.
    
    Args:
        event: Lambda event object containing:
            - audioData: Base64-encoded audio data (required)
            - sampleRate: Audio sample rate in Hz (required)
            - translatedText: Translated text content (required)
            - voiceId: Polly voice ID (optional, default from config)
            - enableSsml: Enable SSML generation (optional, default from config)
            - enableVolumeDetection: Enable volume detection (optional, default from config)
            - enableRateDetection: Enable rate detection (optional, default from config)
        context: Lambda context object
    
    Returns:
        Response dict with statusCode and body containing:
            - audioData: Base64-encoded synthesized audio (MP3)
            - dynamics: Detected audio dynamics (volume, rate)
            - ssmlText: Generated SSML markup
            - processingTimeMs: Total processing time
            - correlationId: Correlation identifier
            - fallbackUsed: Whether plain text fallback was used
            - timing: Breakdown of processing times
    
    Examples:
        >>> event = {
        ...     'audioData': 'base64_encoded_audio...',
        ...     'sampleRate': 16000,
        ...     'translatedText': 'Hello, how are you?',
        ...     'voiceId': 'Joanna'
        ... }
        >>> response = lambda_handler(event, context)
        >>> assert response['statusCode'] == 200
        >>> body = json.loads(response['body'])
        >>> assert 'audioData' in body
        >>> assert 'dynamics' in body
    """
    global orchestrator
    
    try:
        logger.info("Lambda handler invoked for emotion dynamics processing")
        
        # Initialize orchestrator on cold start
        if orchestrator is None:
            logger.info("Cold start: Initializing AudioDynamicsOrchestrator")
            settings = get_settings()
            orchestrator = AudioDynamicsOrchestrator(settings=settings)
            logger.info("AudioDynamicsOrchestrator initialized successfully")
        
        # Parse and validate input event
        try:
            audio_data, sample_rate, translated_text, options = _parse_input_event(event)
        except ValueError as e:
            logger.error(f"Input validation failed: {e}")
            return _error_response(400, 'Invalid input', str(e))
        
        # Process audio and text through orchestrator
        try:
            result = orchestrator.process_audio_and_text(
                audio_data=audio_data,
                sample_rate=sample_rate,
                translated_text=translated_text,
                options=options
            )
            
            logger.info(
                f"Processing completed successfully: "
                f"correlation_id={result.correlation_id}, "
                f"processing_time={result.processing_time_ms}ms"
            )
            
            # Build success response
            return _success_response(result)
            
        except EmotionDynamicsError as e:
            logger.error(f"Emotion dynamics processing failed: {e}", exc_info=True)
            return _error_response(500, 'Processing failed', str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {e}", exc_info=True)
        return _error_response(500, 'Internal server error', str(e))


def _parse_input_event(event: Dict[str, Any]) -> tuple:
    """
    Parse and validate input event.
    
    Validates:
    - Required fields (audioData, sampleRate, translatedText)
    - Audio data format (base64-encoded, valid PCM)
    - Audio data size (not empty, within limits)
    - Sample rate (positive integer, supported values)
    - Text content (non-empty string, within character limits)
    
    Args:
        event: Lambda event object
    
    Returns:
        Tuple of (audio_data, sample_rate, translated_text, options)
    
    Raises:
        ValueError: When input validation fails
    """
    # Extract required fields
    audio_data_b64 = event.get('audioData')
    sample_rate = event.get('sampleRate')
    translated_text = event.get('translatedText')
    
    # Validate required fields
    if not audio_data_b64:
        raise ValueError("Missing required field: audioData")
    
    if not sample_rate:
        raise ValueError("Missing required field: sampleRate")
    
    if not translated_text:
        raise ValueError("Missing required field: translatedText")
    
    # Validate sample rate
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValueError(f"Invalid sampleRate: must be positive integer, got {sample_rate}")
    
    # Validate sample rate is supported (common audio sample rates)
    supported_sample_rates = {8000, 16000, 22050, 24000, 32000, 44100, 48000}
    if sample_rate not in supported_sample_rates:
        logger.warning(
            f"Unusual sample rate: {sample_rate}Hz. "
            f"Supported rates: {sorted(supported_sample_rates)}"
        )
    
    # Validate text
    if not isinstance(translated_text, str):
        raise ValueError(f"Invalid translatedText: must be string, got {type(translated_text)}")
    
    if not translated_text.strip():
        raise ValueError("translatedText contains only whitespace")
    
    # Validate text length (Polly limit is 3000 characters for SSML)
    max_text_length = 3000
    if len(translated_text) > max_text_length:
        raise ValueError(
            f"translatedText exceeds maximum length: "
            f"{len(translated_text)} > {max_text_length} characters"
        )
    
    # Decode audio data
    try:
        audio_bytes = base64.b64decode(audio_data_b64)
    except Exception as e:
        raise ValueError(f"Invalid audioData: failed to decode base64: {e}")
    
    # Validate audio data size
    if len(audio_bytes) == 0:
        raise ValueError("audioData is empty after decoding")
    
    # Validate audio data size limits (max 10MB for Lambda payload)
    max_audio_bytes = 10 * 1024 * 1024  # 10MB
    if len(audio_bytes) > max_audio_bytes:
        raise ValueError(
            f"audioData exceeds maximum size: "
            f"{len(audio_bytes)} > {max_audio_bytes} bytes"
        )
    
    # Convert to numpy array (assuming 16-bit PCM)
    try:
        audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    except Exception as e:
        raise ValueError(f"Invalid audioData: failed to convert to numpy array: {e}")
    
    # Validate audio array
    if audio_data.size == 0:
        raise ValueError("audioData array is empty")
    
    # Validate audio duration (max 30 seconds for reasonable processing)
    audio_duration_s = audio_data.size / sample_rate
    max_audio_duration_s = 30.0
    if audio_duration_s > max_audio_duration_s:
        raise ValueError(
            f"audioData duration exceeds maximum: "
            f"{audio_duration_s:.1f}s > {max_audio_duration_s}s"
        )
    
    # Validate audio is not too short (min 0.1 seconds)
    min_audio_duration_s = 0.1
    if audio_duration_s < min_audio_duration_s:
        raise ValueError(
            f"audioData duration too short: "
            f"{audio_duration_s:.3f}s < {min_audio_duration_s}s"
        )
    
    # Extract optional processing options
    voice_id = event.get('voiceId')
    enable_ssml = event.get('enableSsml')
    enable_volume_detection = event.get('enableVolumeDetection')
    enable_rate_detection = event.get('enableRateDetection')
    
    # Create processing options (None values will use defaults from settings)
    options = ProcessingOptions(
        voice_id=voice_id,
        enable_ssml=enable_ssml,
        enable_volume_detection=enable_volume_detection,
        enable_rate_detection=enable_rate_detection
    )
    
    logger.debug(
        f"Input parsed successfully: "
        f"audio_samples={audio_data.size}, "
        f"sample_rate={sample_rate}, "
        f"text_length={len(translated_text)}, "
        f"voice_id={options.voice_id}"
    )
    
    return audio_data, sample_rate, translated_text, options


def _success_response(result) -> Dict[str, Any]:
    """
    Build success response from ProcessingResult.
    
    Args:
        result: ProcessingResult object
    
    Returns:
        Lambda response dict with statusCode 200
    """
    # Encode audio stream to base64
    audio_data_b64 = base64.b64encode(result.audio_stream).decode('utf-8')
    
    # Build response body
    body = {
        'audioData': audio_data_b64,
        'dynamics': {
            'volume': {
                'level': result.dynamics.volume.level,
                'dbValue': result.dynamics.volume.db_value
            },
            'rate': {
                'classification': result.dynamics.rate.classification,
                'wpm': result.dynamics.rate.wpm,
                'onsetCount': result.dynamics.rate.onset_count
            }
        },
        'ssmlText': result.ssml_text,
        'processingTimeMs': result.processing_time_ms,
        'correlationId': result.correlation_id,
        'fallbackUsed': result.fallback_used,
        'timing': {
            'volumeDetectionMs': result.volume_detection_ms,
            'rateDetectionMs': result.rate_detection_ms,
            'ssmlGenerationMs': result.ssml_generation_ms,
            'pollySynthesisMs': result.polly_synthesis_ms
        }
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(body)
    }


def _error_response(status_code: int, error_type: str, message: str) -> Dict[str, Any]:
    """
    Build error response.
    
    Args:
        status_code: HTTP status code
        error_type: Error type description
        message: Error message
    
    Returns:
        Lambda response dict with error details
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'error': error_type,
            'message': message
        })
    }
