"""
Parallel Translation Service.

This module provides concurrent translation functionality using AWS Translate
with cache-first lookups to minimize costs and latency.
"""

import asyncio
from typing import Dict, List, Tuple, Optional
import boto3
from botocore.exceptions import ClientError

from .translation_cache_manager import TranslationCacheManager


class ParallelTranslationService:
    """
    Executes concurrent translations with caching.
    
    Translates text to multiple target languages in parallel using AWS Translate,
    with cache-first lookups to reduce costs and latency. Handles errors gracefully
    by skipping failed languages and continuing with others.
    """
    
    def __init__(
        self,
        cache_manager: TranslationCacheManager,
        translate_client=None,
        timeout_seconds: int = 2
    ):
        """
        Initialize Parallel Translation Service.
        
        Args:
            cache_manager: Translation cache manager instance
            translate_client: Optional AWS Translate client for testing
            timeout_seconds: Timeout per translation call (default: 2)
        """
        self.cache_manager = cache_manager
        self.translate_client = translate_client or boto3.client('translate')
        self.timeout_seconds = timeout_seconds
    
    def translate_to_languages(
        self,
        source_lang: str,
        text: str,
        target_languages: List[str],
        session_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Translate text to multiple languages in parallel.
        
        Uses asyncio.gather() for concurrent AWS Translate API calls.
        Integrates cache manager for cache-first lookups.
        Handles cache misses with AWS Translate API calls.
        Stores successful translations in cache.
        
        Args:
            source_lang: Source language code (ISO 639-1)
            text: Text to translate
            target_languages: List of target language codes
            session_id: Optional session ID for logging context
            
        Returns:
            Dictionary mapping language code to translated text.
            Failed languages are omitted from results.
        """
        # Run async translation in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(
                self._translate_all_languages(
                    source_lang,
                    text,
                    target_languages,
                    session_id
                )
            )
            return results
        finally:
            loop.close()
    
    async def _translate_all_languages(
        self,
        source_lang: str,
        text: str,
        target_languages: List[str],
        session_id: Optional[str]
    ) -> Dict[str, str]:
        """
        Translate to all target languages concurrently.
        
        Args:
            source_lang: Source language code
            text: Text to translate
            target_languages: List of target language codes
            session_id: Optional session ID for logging
            
        Returns:
            Dictionary mapping language code to translated text
        """
        # Create tasks for all languages
        tasks = [
            self._translate_single(source_lang, target_lang, text, session_id)
            for target_lang in target_languages
        ]
        
        # Execute all translations in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build result dictionary, filtering out failures
        translations = {}
        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                lang, translation = result
                if translation is not None:
                    translations[lang] = translation
        
        return translations
    
    async def _translate_single(
        self,
        source_lang: str,
        target_lang: str,
        text: str,
        session_id: Optional[str]
    ) -> Tuple[str, Optional[str]]:
        """
        Translate to single language with cache check.
        
        Implements cache-first lookup strategy:
        1. Check cache for existing translation
        2. If cache miss, call AWS Translate
        3. Store successful translation in cache
        
        Handles errors gracefully:
        - Catches AWS Translate ClientError exceptions
        - Logs errors with session context
        - Returns None for failed translations
        
        Implements timeout handling:
        - Sets 2-second timeout per translation call
        - Handles timeout exceptions gracefully
        - Logs timeout events with context
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            text: Text to translate
            session_id: Optional session ID for logging
            
        Returns:
            Tuple of (target_lang, translated_text) or (target_lang, None) on failure
        """
        try:
            # Check cache first
            cached_translation = self.cache_manager.get_cached_translation(
                source_lang,
                target_lang,
                text
            )
            
            if cached_translation:
                # Cache hit - return cached translation
                return (target_lang, cached_translation)
            
            # Cache miss - call AWS Translate with timeout
            translation = await asyncio.wait_for(
                self._call_translate_api(source_lang, target_lang, text),
                timeout=self.timeout_seconds
            )
            
            # Store successful translation in cache
            if translation:
                self.cache_manager.cache_translation(
                    source_lang,
                    target_lang,
                    text,
                    translation
                )
            
            return (target_lang, translation)
            
        except asyncio.TimeoutError:
            # Handle timeout gracefully
            context = f"session_id={session_id}, " if session_id else ""
            print(
                f"Translation timeout: {context}"
                f"source={source_lang}, target={target_lang}, "
                f"timeout={self.timeout_seconds}s"
            )
            return (target_lang, None)
            
        except ClientError as e:
            # Handle AWS Translate errors gracefully
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            context = f"session_id={session_id}, " if session_id else ""
            print(
                f"Translation failed: {context}"
                f"source={source_lang}, target={target_lang}, "
                f"error={error_code}, message={str(e)}"
            )
            return (target_lang, None)
            
        except Exception as e:
            # Handle unexpected errors
            context = f"session_id={session_id}, " if session_id else ""
            print(
                f"Unexpected translation error: {context}"
                f"source={source_lang}, target={target_lang}, "
                f"error={type(e).__name__}, message={str(e)}"
            )
            return (target_lang, None)
    
    async def _call_translate_api(
        self,
        source_lang: str,
        target_lang: str,
        text: str
    ) -> Optional[str]:
        """
        Call AWS Translate API asynchronously.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            text: Text to translate
            
        Returns:
            Translated text or None on failure
        """
        # Run synchronous boto3 call in executor to avoid blocking
        loop = asyncio.get_event_loop()
        
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.translate_client.translate_text(
                    Text=text,
                    SourceLanguageCode=source_lang,
                    TargetLanguageCode=target_lang
                )
            )
            
            return response.get('TranslatedText')
            
        except Exception:
            # Let caller handle the exception
            raise
