"""
SSML Generator for Amazon Polly speech synthesis.

Generates Speech Synthesis Markup Language (SSML) with prosody tags
based on detected audio dynamics (volume and speaking rate).
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional

from emotion_dynamics.models.audio_dynamics import AudioDynamics
from emotion_dynamics.exceptions import SSMLValidationError


logger = logging.getLogger(__name__)


class SSMLGenerator:
    """
    Generator for SSML markup with prosody tags.
    
    Maps audio dynamics (volume and speaking rate) to SSML prosody attributes
    and generates valid SSML markup conforming to Amazon Polly specification v1.1.
    """
    
    # SSML namespace for validation
    SSML_NAMESPACE = "http://www.w3.org/2001/10/synthesis"
    
    # Valid SSML prosody attribute values
    VALID_VOLUME_VALUES = {'silent', 'x-soft', 'soft', 'medium', 'loud', 'x-loud'}
    VALID_RATE_VALUES = {'x-slow', 'slow', 'medium', 'fast', 'x-fast'}
    
    def __init__(self):
        """Initialize SSML generator."""
        pass
    
    def generate_ssml(
        self,
        text: str,
        dynamics: Optional[AudioDynamics] = None
    ) -> str:
        """
        Generate SSML markup with prosody tags based on audio dynamics.
        
        Args:
            text: Translated text content to wrap in SSML
            dynamics: Audio dynamics (volume and rate). If None, returns plain text.
        
        Returns:
            Valid SSML markup string with prosody tags, or plain text on validation error
        
        Raises:
            SSMLValidationError: When SSML generation produces invalid markup
        """
        # Handle None or empty text
        if not text:
            logger.warning("Empty text provided to SSML generator")
            return ""
        
        # Handle None dynamics - return plain text wrapped in speak tags
        if dynamics is None:
            logger.debug("No dynamics provided, generating plain SSML")
            return self._generate_plain_ssml(text)
        
        try:
            # Escape XML special characters in text
            escaped_text = self._escape_xml(text)
            
            # Get SSML prosody attributes from dynamics
            attributes = dynamics.to_ssml_attributes()
            volume = attributes['volume']
            rate = attributes['rate']
            
            # Validate prosody attribute values
            self._validate_prosody_attributes(volume, rate)
            
            # Generate SSML markup
            ssml = self._build_ssml_markup(escaped_text, volume, rate)
            
            # Validate generated SSML
            self._validate_ssml(ssml)
            
            logger.debug(
                f"Generated SSML with volume={volume}, rate={rate}",
                extra={
                    'volume': volume,
                    'rate': rate,
                    'text_length': len(text),
                    'correlation_id': dynamics.correlation_id
                }
            )
            
            return ssml
            
        except SSMLValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            # Log error and fall back to plain text
            logger.error(
                f"SSML generation failed: {e}",
                extra={
                    'error': str(e),
                    'text_length': len(text) if text else 0
                },
                exc_info=True
            )
            # Fall back to plain text
            return self._generate_plain_ssml(text)
    
    def _escape_xml(self, text: str) -> str:
        """
        Escape XML special characters in text content.
        
        Args:
            text: Raw text content
        
        Returns:
            Text with XML special characters escaped
        """
        # Escape XML special characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        
        return text
    
    def _validate_prosody_attributes(self, volume: str, rate: str) -> None:
        """
        Validate prosody attribute values against SSML specification.
        
        Args:
            volume: Volume attribute value
            rate: Rate attribute value
        
        Raises:
            SSMLValidationError: When attribute values are invalid
        """
        if volume not in self.VALID_VOLUME_VALUES:
            raise SSMLValidationError(
                f"Invalid volume attribute: {volume}. "
                f"Must be one of {self.VALID_VOLUME_VALUES}"
            )
        
        if rate not in self.VALID_RATE_VALUES:
            raise SSMLValidationError(
                f"Invalid rate attribute: {rate}. "
                f"Must be one of {self.VALID_RATE_VALUES}"
            )
    
    def _build_ssml_markup(self, text: str, volume: str, rate: str) -> str:
        """
        Build SSML markup with prosody tags.
        
        Args:
            text: Escaped text content
            volume: SSML volume attribute value
            rate: SSML rate attribute value
        
        Returns:
            Complete SSML markup string
        """
        ssml = (
            f'<speak>'
            f'<prosody rate="{rate}" volume="{volume}">'
            f'{text}'
            f'</prosody>'
            f'</speak>'
        )
        return ssml
    
    def _generate_plain_ssml(self, text: str) -> str:
        """
        Generate plain SSML without prosody tags.
        
        Args:
            text: Text content
        
        Returns:
            SSML with text wrapped in speak tags only
        """
        escaped_text = self._escape_xml(text)
        return f'<speak>{escaped_text}</speak>'
    
    def _validate_ssml(self, ssml: str) -> None:
        """
        Validate SSML markup structure.
        
        Args:
            ssml: SSML markup string
        
        Raises:
            SSMLValidationError: When SSML structure is invalid
        """
        try:
            # Parse SSML as XML
            root = ET.fromstring(ssml)
            
            # Validate root element is 'speak'
            if root.tag != 'speak':
                raise SSMLValidationError(
                    f"Root element must be 'speak', got '{root.tag}'"
                )
            
            # If prosody tags exist, validate structure
            prosody_elements = root.findall('.//prosody')
            for prosody in prosody_elements:
                # Validate required attributes exist
                if 'rate' not in prosody.attrib:
                    raise SSMLValidationError("Prosody element missing 'rate' attribute")
                if 'volume' not in prosody.attrib:
                    raise SSMLValidationError("Prosody element missing 'volume' attribute")
                
                # Validate attribute values
                rate = prosody.attrib['rate']
                volume = prosody.attrib['volume']
                
                if rate not in self.VALID_RATE_VALUES:
                    raise SSMLValidationError(f"Invalid rate value in SSML: {rate}")
                if volume not in self.VALID_VOLUME_VALUES:
                    raise SSMLValidationError(f"Invalid volume value in SSML: {volume}")
            
        except ET.ParseError as e:
            raise SSMLValidationError(f"Invalid XML structure: {e}")
        except SSMLValidationError:
            # Re-raise our validation errors
            raise
        except Exception as e:
            raise SSMLValidationError(f"SSML validation failed: {e}")
