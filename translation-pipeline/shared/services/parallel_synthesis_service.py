"""Parallel Synthesis Service for AWS Polly TTS."""

import asyncio
import logging
from typing import Dict, List, Tuple, Optional
import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


class ParallelSynthesisService:
    """
    Synthesizes SSML text to audio using AWS Polly in parallel.
    
    Handles multiple languages concurrently with error handling and timeout support.
    """
    
    # Neural voice mapping for supported languages
    NEURAL_VOICES = {
        "en": "Joanna",
        "es": "Lupe",
        "fr": "Lea",
        "de": "Vicki",
        "it": "Bianca",
        "pt": "Camila",
        "ja": "Takumi",
        "ko": "Seoyeon",
        "zh": "Zhiyu",
        "ar": "Zeina",
        "hi": "Aditi",
        "nl": "Laura",
        "pl": "Ola",
        "ru": "Tatyana",
        "sv": "Astrid",
        "tr": "Filiz"
    }
    
    # Default timeout for synthesis operations (seconds)
    DEFAULT_TIMEOUT = 5.0
    
    def __init__(
        self,
        polly_client: Optional[boto3.client] = None,
        timeout: float = DEFAULT_TIMEOUT
    ):
        """
        Initialize Parallel Synthesis Service.
        
        Args:
            polly_client: Optional boto3 Polly client (creates default if None)
            timeout: Timeout for synthesis operations in seconds
        """
        self.polly_client = polly_client or boto3.client('polly')
        self.timeout = timeout
    
    async def synthesize_to_languages(
        self,
        ssml_by_language: Dict[str, str],
        session_id: Optional[str] = None
    ) -> Dict[str, bytes]:
        """
        Synthesize SSML to audio for multiple languages in parallel.
        
        Args:
            ssml_by_language: Dictionary mapping language code to SSML text
            session_id: Optional session ID for logging context
            
        Returns:
            Dictionary mapping language code to PCM audio bytes
            Only includes successfully synthesized languages
            
        Example:
            >>> service = ParallelSynthesisService()
            >>> ssml_texts = {
            ...     "es": "<speak>Hola</speak>",
            ...     "fr": "<speak>Bonjour</speak>"
            ... }
            >>> audio_results = await service.synthesize_to_languages(ssml_texts)
            >>> print(audio_results.keys())
            dict_keys(['es', 'fr'])
        """
        if not ssml_by_language:
            logger.warning("No SSML texts provided for synthesis")
            return {}
        
        # Create synthesis tasks for all languages
        tasks = [
            self._synthesize_single(language, ssml, session_id)
            for language, ssml in ssml_by_language.items()
        ]
        
        # Execute all synthesis operations in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        audio_by_language = {}
        failed_languages = []
        
        for result in results:
            if isinstance(result, Exception):
                # Log exception but continue with other languages
                logger.error(
                    f"Synthesis failed with exception: {result}",
                    extra={'session_id': session_id}
                )
                continue
            
            if result is not None:
                language, audio_bytes = result
                audio_by_language[language] = audio_bytes
            else:
                # None indicates a failed synthesis
                failed_languages.append("unknown")
        
        # Log summary
        logger.info(
            f"Synthesis completed: {len(audio_by_language)} succeeded, "
            f"{len(failed_languages)} failed",
            extra={
                'session_id': session_id,
                'succeeded_languages': list(audio_by_language.keys()),
                'failed_count': len(failed_languages)
            }
        )
        
        return audio_by_language
    
    async def _synthesize_single(
        self,
        language: str,
        ssml: str,
        session_id: Optional[str] = None
    ) -> Optional[Tuple[str, bytes]]:
        """
        Synthesize single language with AWS Polly.
        
        Args:
            language: ISO 639-1 language code
            ssml: SSML text to synthesize
            session_id: Optional session ID for logging
            
        Returns:
            Tuple of (language, audio_bytes) or None if failed
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Get voice for language
            voice_id = self._get_voice_for_language(language)
            
            # Call AWS Polly with timeout
            response = await asyncio.wait_for(
                self._call_polly(voice_id, ssml),
                timeout=self.timeout
            )
            
            # Read audio stream
            audio_bytes = response['AudioStream'].read()
            
            # Calculate duration
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            logger.info(
                f"Synthesis succeeded for {language}",
                extra={
                    'session_id': session_id,
                    'language': language,
                    'voice_id': voice_id,
                    'duration_ms': duration_ms,
                    'audio_size_bytes': len(audio_bytes)
                }
            )
            
            return (language, audio_bytes)
            
        except asyncio.TimeoutError:
            logger.error(
                f"Synthesis timeout for {language} after {self.timeout}s",
                extra={
                    'session_id': session_id,
                    'language': language,
                    'timeout_seconds': self.timeout
                }
            )
            return None
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(
                f"AWS Polly error for {language}: {error_code}",
                extra={
                    'session_id': session_id,
                    'language': language,
                    'error_code': error_code,
                    'error_message': str(e)
                }
            )
            return None
            
        except Exception as e:
            logger.error(
                f"Unexpected error during synthesis for {language}: {e}",
                extra={
                    'session_id': session_id,
                    'language': language,
                    'error_type': type(e).__name__
                },
                exc_info=True
            )
            return None
    
    async def _call_polly(self, voice_id: str, ssml: str) -> dict:
        """
        Call AWS Polly SynthesizeSpeech API asynchronously.
        
        Args:
            voice_id: Polly voice ID
            ssml: SSML text to synthesize
            
        Returns:
            Polly response dictionary
        """
        loop = asyncio.get_event_loop()
        
        # Run boto3 call in thread pool to avoid blocking
        response = await loop.run_in_executor(
            None,
            lambda: self.polly_client.synthesize_speech(
                Text=ssml,
                TextType='ssml',
                OutputFormat='pcm',
                VoiceId=voice_id,
                Engine='neural',
                SampleRate='16000'
            )
        )
        
        return response
    
    def _get_voice_for_language(self, language: str) -> str:
        """
        Get neural voice ID for language.
        
        Args:
            language: ISO 639-1 language code
            
        Returns:
            Polly voice ID
            
        Raises:
            ValueError: If language not supported
        """
        voice_id = self.NEURAL_VOICES.get(language)
        
        if voice_id is None:
            raise ValueError(
                f"Language '{language}' not supported. "
                f"Supported languages: {list(self.NEURAL_VOICES.keys())}"
            )
        
        return voice_id
