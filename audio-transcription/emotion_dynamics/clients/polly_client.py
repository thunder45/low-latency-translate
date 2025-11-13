"""
Amazon Polly client for SSML-enhanced speech synthesis.

This module provides a client for Amazon Polly that synthesizes speech from
SSML markup with support for neural voices, exponential backoff retry logic,
and graceful fallback to plain text.
"""

import logging
import time
import random
from typing import Optional, Dict, Any
from io import BytesIO

import boto3
from botocore.exceptions import ClientError

from emotion_dynamics.exceptions import SynthesisError


logger = logging.getLogger(__name__)


class PollyClient:
    """
    Client for Amazon Polly speech synthesis with SSML support.
    
    This client handles:
    - SSML synthesis with neural voices
    - MP3 output at 24000 Hz sample rate
    - Exponential backoff retry logic for throttling
    - Fallback to plain text on SSML rejection
    - Audio stream handling
    
    Attributes:
        polly_client: Boto3 Polly client
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay for exponential backoff in seconds (default: 0.1)
        max_delay: Maximum delay for exponential backoff in seconds (default: 2.0)
    """
    
    # Retry configuration
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 0.1  # 100ms
    DEFAULT_MAX_DELAY = 2.0   # 2s
    
    # Polly configuration
    DEFAULT_VOICE_ID = 'Joanna'
    DEFAULT_ENGINE = 'neural'
    DEFAULT_OUTPUT_FORMAT = 'mp3'
    DEFAULT_SAMPLE_RATE = '24000'
    
    # Retryable error codes
    RETRYABLE_ERRORS = {
        'ThrottlingException',
        'ServiceFailureException',
        'ServiceUnavailableException'
    }
    
    def __init__(
        self,
        region_name: Optional[str] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY
    ):
        """
        Initialize Polly client.
        
        Args:
            region_name: AWS region name (uses default if not specified)
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff in seconds
            max_delay: Maximum delay for exponential backoff in seconds
        """
        self.polly_client = boto3.client('polly', region_name=region_name)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        
        logger.info(
            f"Initialized PollyClient with max_retries={max_retries}, "
            f"base_delay={base_delay}s, max_delay={max_delay}s"
        )
    
    def synthesize_speech(
        self,
        text: str,
        voice_id: str = DEFAULT_VOICE_ID,
        text_type: str = 'ssml',
        output_format: str = DEFAULT_OUTPUT_FORMAT,
        sample_rate: str = DEFAULT_SAMPLE_RATE,
        engine: str = DEFAULT_ENGINE
    ) -> bytes:
        """
        Synthesize speech from text or SSML markup.
        
        This method:
        1. Attempts synthesis with specified text_type (ssml or text)
        2. Implements exponential backoff retry for throttling errors
        3. Falls back to plain text if SSML is rejected
        4. Returns audio stream as bytes
        
        Args:
            text: Text or SSML markup to synthesize
            voice_id: Polly neural voice ID (default: 'Joanna')
            text_type: 'ssml' or 'text' (default: 'ssml')
            output_format: Audio format (default: 'mp3')
            sample_rate: Sample rate in Hz (default: '24000')
            engine: Polly engine type (default: 'neural')
            
        Returns:
            Audio stream as bytes in specified format
            
        Raises:
            SynthesisError: When synthesis fails after all retry attempts
                           and fallback (if applicable)
        """
        # Validate inputs
        if not text or not text.strip():
            raise SynthesisError("Text cannot be empty")
        
        # Try synthesis with retries
        attempt = 0
        last_error = None
        
        while attempt <= self.max_retries:
            try:
                logger.debug(
                    f"Attempting Polly synthesis (attempt {attempt + 1}/{self.max_retries + 1}): "
                    f"text_type={text_type}, voice_id={voice_id}, "
                    f"text_length={len(text)}"
                )
                
                # Call Polly API
                response = self.polly_client.synthesize_speech(
                    Text=text,
                    TextType=text_type,
                    OutputFormat=output_format,
                    VoiceId=voice_id,
                    Engine=engine,
                    SampleRate=sample_rate
                )
                
                # Read audio stream
                audio_stream = response['AudioStream'].read()
                
                logger.info(
                    f"Polly synthesis successful: "
                    f"text_type={text_type}, voice_id={voice_id}, "
                    f"audio_size={len(audio_stream)} bytes"
                )
                
                return audio_stream
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                last_error = e
                
                # Check if error is retryable
                if error_code in self.RETRYABLE_ERRORS:
                    if attempt < self.max_retries:
                        # Calculate delay with exponential backoff and jitter
                        delay = min(
                            self.base_delay * (2 ** attempt),
                            self.max_delay
                        )
                        # Add jitter (±25%)
                        jitter = delay * 0.25 * (2 * random.random() - 1)
                        delay_with_jitter = max(0, delay + jitter)
                        
                        logger.warning(
                            f"Polly {error_code} on attempt {attempt + 1}, "
                            f"retrying in {delay_with_jitter:.2f}s"
                        )
                        
                        time.sleep(delay_with_jitter)
                        attempt += 1
                        continue
                    else:
                        logger.error(
                            f"Polly {error_code} after {self.max_retries} retries"
                        )
                        raise SynthesisError(
                            f"Synthesis failed after {self.max_retries} retries: {error_code}"
                        ) from e
                
                # Check if SSML was rejected and we can fallback
                elif text_type == 'ssml' and error_code in [
                    'InvalidSsmlException',
                    'SsmlMarksNotSupportedForInputTypeException'
                ]:
                    logger.warning(
                        f"Polly rejected SSML ({error_code}), "
                        f"falling back to plain text"
                    )
                    
                    # Extract plain text from SSML
                    plain_text = self._extract_text_from_ssml(text)
                    
                    # Retry with plain text (recursive call with text_type='text')
                    return self.synthesize_speech(
                        text=plain_text,
                        voice_id=voice_id,
                        text_type='text',
                        output_format=output_format,
                        sample_rate=sample_rate,
                        engine=engine
                    )
                
                # Non-retryable error
                else:
                    logger.error(
                        f"Polly synthesis failed with non-retryable error: {error_code}"
                    )
                    raise SynthesisError(
                        f"Synthesis failed: {error_code}"
                    ) from e
            
            except Exception as e:
                logger.error(f"Unexpected error during Polly synthesis: {e}")
                raise SynthesisError(f"Synthesis failed: {str(e)}") from e
        
        # Should not reach here, but handle just in case
        if last_error:
            raise SynthesisError(
                f"Synthesis failed after {self.max_retries} retries"
            ) from last_error
        else:
            raise SynthesisError("Synthesis failed for unknown reason")
    
    def _extract_text_from_ssml(self, ssml_text: str) -> str:
        """
        Extract plain text from SSML markup.
        
        This is a simple extraction that removes XML tags. For production use,
        consider using an XML parser for more robust extraction.
        
        Args:
            ssml_text: SSML markup string
            
        Returns:
            Plain text without XML tags
        """
        import re
        
        # Remove XML tags
        text = re.sub(r'<[^>]+>', '', ssml_text)
        
        # Decode common XML entities
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&amp;', '&')
        text = text.replace('&quot;', '"')
        text = text.replace('&apos;', "'")
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def get_available_voices(
        self,
        language_code: Optional[str] = None,
        engine: str = DEFAULT_ENGINE
    ) -> list:
        """
        Get list of available Polly voices.
        
        Args:
            language_code: Filter by language code (e.g., 'en-US')
            engine: Filter by engine type (default: 'neural')
            
        Returns:
            List of voice dictionaries with Id, Name, LanguageCode, etc.
        """
        try:
            params = {}
            if language_code:
                params['LanguageCode'] = language_code
            if engine:
                params['Engine'] = engine
            
            response = self.polly_client.describe_voices(**params)
            return response.get('Voices', [])
            
        except ClientError as e:
            logger.error(f"Failed to get available voices: {e}")
            return []
