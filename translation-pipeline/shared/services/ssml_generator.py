"""SSML Generator for emotion-aware speech synthesis."""

import html
from typing import Dict
from ..models.emotion_dynamics import EmotionDynamics


class SSMLGenerator:
    """
    Generates SSML markup from translated text and emotion dynamics.
    
    Applies prosody tags for rate and volume, and emphasis tags for emotion.
    """
    
    # Mapping from WPM ranges to SSML rate values
    RATE_MAPPING = {
        (0, 120): "slow",
        (120, 150): "medium",
        (150, 170): "medium",
        (170, 200): "fast",
        (200, float('inf')): "x-fast"
    }
    
    # Mapping from volume levels to SSML volume values
    VOLUME_MAPPING = {
        "whisper": "x-soft",
        "soft": "soft",
        "normal": "medium",
        "loud": "loud"
    }
    
    # Emotions that trigger strong emphasis
    STRONG_EMPHASIS_EMOTIONS = {"angry", "excited", "surprised"}
    
    # Emotions that trigger pauses
    PAUSE_EMOTIONS = {"sad", "fearful"}
    
    def generate_ssml(
        self,
        text: str,
        emotion_dynamics: EmotionDynamics
    ) -> str:
        """
        Generate SSML with emotion and dynamics applied.
        
        Args:
            text: Translated text to enhance with SSML
            emotion_dynamics: Detected emotion and speaking characteristics
            
        Returns:
            SSML-formatted text ready for AWS Polly
            
        Example:
            >>> dynamics = EmotionDynamics(
            ...     emotion="angry",
            ...     intensity=0.8,
            ...     rate_wpm=185,
            ...     volume_level="loud"
            ... )
            >>> generator = SSMLGenerator()
            >>> ssml = generator.generate_ssml("Hello everyone", dynamics)
            >>> print(ssml)
            <speak>
              <prosody rate="fast">
                <prosody volume="loud">
                  <emphasis level="strong">Hello everyone</emphasis>
                </prosody>
              </prosody>
            </speak>
        """
        # Escape XML reserved characters
        escaped_text = self._escape_xml(text)
        
        # Apply emotion emphasis
        enhanced_text = self._apply_emotion_emphasis(
            escaped_text,
            emotion_dynamics.emotion,
            emotion_dynamics.intensity
        )
        
        # Map rate and volume to SSML values
        rate = self._map_rate_to_ssml(emotion_dynamics.rate_wpm)
        volume = self._map_volume_to_ssml(emotion_dynamics.volume_level)
        
        # Generate complete SSML document
        ssml = f"""<speak>
  <prosody rate="{rate}">
    <prosody volume="{volume}">
      {enhanced_text}
    </prosody>
  </prosody>
</speak>"""
        
        return ssml
    
    def _escape_xml(self, text: str) -> str:
        """
        Escape XML reserved characters in text.
        
        Escapes: &, <, >, ", '
        
        Args:
            text: Text to escape
            
        Returns:
            XML-escaped text
        """
        return html.escape(text, quote=True)
    
    def _map_rate_to_ssml(self, wpm: int) -> str:
        """
        Map speaking rate (WPM) to SSML prosody rate values.
        
        Mapping:
        - 0-120 WPM: "slow"
        - 120-150 WPM: "medium"
        - 150-170 WPM: "medium"
        - 170-200 WPM: "fast"
        - 200+ WPM: "x-fast"
        
        Args:
            wpm: Words per minute
            
        Returns:
            SSML rate value
        """
        for (min_wpm, max_wpm), rate in self.RATE_MAPPING.items():
            if min_wpm <= wpm < max_wpm:
                return rate
        
        # Default to medium if somehow not matched
        return "medium"
    
    def _map_volume_to_ssml(self, volume_level: str) -> str:
        """
        Map volume level to SSML prosody volume values.
        
        Mapping:
        - "whisper": "x-soft"
        - "soft": "soft"
        - "normal": "medium"
        - "loud": "loud"
        
        Args:
            volume_level: Volume level string
            
        Returns:
            SSML volume value
        """
        return self.VOLUME_MAPPING.get(volume_level, "medium")
    
    def _apply_emotion_emphasis(
        self,
        text: str,
        emotion: str,
        intensity: float
    ) -> str:
        """
        Apply emphasis tags based on emotion type and intensity.
        
        Rules:
        - Strong emphasis: angry, excited, surprised with intensity > 0.7
        - Pauses: sad, fearful emotions get break tags
        - Otherwise: no emphasis
        
        Args:
            text: Text to enhance
            emotion: Emotion type
            intensity: Emotion intensity (0.0 to 1.0)
            
        Returns:
            Text with emotion emphasis applied
        """
        # Apply strong emphasis for high-intensity strong emotions
        if emotion in self.STRONG_EMPHASIS_EMOTIONS and intensity > 0.7:
            return f'<emphasis level="strong">{text}</emphasis>'
        
        # Apply pauses for sad/fearful emotions
        if emotion in self.PAUSE_EMOTIONS:
            # Add a short pause before the text
            return f'<break time="300ms"/>{text}'
        
        # No emphasis for other emotions
        return text
