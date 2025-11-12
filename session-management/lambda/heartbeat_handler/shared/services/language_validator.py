"""
Language support validation service.

Validates that target languages are supported by both AWS Translate and AWS Polly.
"""
import boto3
import logging
from functools import lru_cache
from typing import Set, Tuple, Optional

logger = logging.getLogger(__name__)


class UnsupportedLanguageError(Exception):
    """Raised when a language is not supported."""
    
    def __init__(self, message: str, language_code: str):
        """
        Initialize unsupported language error.
        
        Args:
            message: Error message
            language_code: Language code that is not supported
        """
        super().__init__(message)
        self.language_code = language_code
        self.message = message


class LanguageValidator:
    """
    Validates language support for AWS Translate and Polly.
    
    Uses caching to minimize API calls and improve performance.
    """
    
    def __init__(self, region: Optional[str] = None):
        """
        Initialize language validator.
        
        Args:
            region: AWS region (defaults to environment or us-east-1)
        """
        self.region = region or 'us-east-1'
        self.translate_client = boto3.client('translate', region_name=self.region)
        self.polly_client = boto3.client('polly', region_name=self.region)
    
    @lru_cache(maxsize=1)
    def get_supported_languages(self) -> dict:
        """
        Get supported languages from AWS services (cached).
        
        Returns:
            dict: {
                'translate': set of supported language codes,
                'polly': set of supported language codes with neural voices
            }
        """
        try:
            # Get AWS Translate supported languages
            translate_response = self.translate_client.list_languages()
            translate_languages = {
                lang['LanguageCode'] 
                for lang in translate_response.get('Languages', [])
            }
            
            logger.info(f"Loaded {len(translate_languages)} languages from AWS Translate")
            
            # Get AWS Polly neural voices
            polly_response = self.polly_client.describe_voices(Engine='neural')
            polly_languages = {
                voice['LanguageCode'][:2]  # Extract 2-letter code from locale
                for voice in polly_response.get('Voices', [])
            }
            
            logger.info(f"Loaded {len(polly_languages)} languages from AWS Polly neural voices")
            
            return {
                'translate': translate_languages,
                'polly': polly_languages
            }
        
        except Exception as e:
            logger.error(f"Failed to load supported languages: {e}")
            # Return empty sets to fail closed
            return {
                'translate': set(),
                'polly': set()
            }
    
    def validate_language_pair(
        self,
        source_language: str,
        target_language: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that source→target translation is supported.
        
        Args:
            source_language: ISO 639-1 source language code
            target_language: ISO 639-1 target language code
        
        Returns:
            tuple: (is_valid, error_message)
        """
        supported = self.get_supported_languages()
        
        # Check AWS Translate support for source language
        if source_language not in supported['translate']:
            error_msg = (
                f"Source language '{source_language}' is not supported by AWS Translate"
            )
            logger.warning(error_msg)
            return False, error_msg
        
        # Check AWS Translate support for target language
        if target_language not in supported['translate']:
            error_msg = (
                f"Target language '{target_language}' is not supported by AWS Translate"
            )
            logger.warning(error_msg)
            return False, error_msg
        
        # Check AWS Polly neural voice support for target language
        if target_language not in supported['polly']:
            error_msg = (
                f"Target language '{target_language}' does not have neural voice "
                f"support in AWS Polly"
            )
            logger.warning(error_msg)
            return False, error_msg
        
        logger.debug(
            f"Language pair validated: {source_language} → {target_language}"
        )
        return True, None
    
    def validate_target_language(
        self,
        source_language: str,
        target_language: str
    ) -> None:
        """
        Validate target language support and raise exception if not supported.
        
        Args:
            source_language: ISO 639-1 source language code
            target_language: ISO 639-1 target language code
        
        Raises:
            UnsupportedLanguageError: If language pair is not supported
        """
        is_valid, error_message = self.validate_language_pair(
            source_language, target_language
        )
        
        if not is_valid:
            raise UnsupportedLanguageError(error_message, target_language)
    
    def get_supported_target_languages(self, source_language: str) -> Set[str]:
        """
        Get all supported target languages for a given source language.
        
        Args:
            source_language: ISO 639-1 source language code
        
        Returns:
            Set of supported target language codes
        """
        supported = self.get_supported_languages()
        
        # Target languages must be supported by both Translate and Polly
        # and source must be supported by Translate
        if source_language not in supported['translate']:
            return set()
        
        return supported['translate'].intersection(supported['polly'])
