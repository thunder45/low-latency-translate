"""
Transcription result data models.

This module defines dataclasses for partial and final transcription results
from AWS Transcribe, along with buffered results and metadata.
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class PartialResult:
    """
    Represents a partial transcription result from AWS Transcribe.
    
    Partial results are intermediate outputs that may change as more audio
    context is received. They include a stability score indicating the
    likelihood that the text will not change.
    
    Attributes:
        result_id: Unique identifier for this result
        text: Transcribed text
        stability_score: Confidence metric (0.0-1.0), None if unavailable
        timestamp: Unix timestamp (seconds) when result was generated
        is_partial: Always True for partial results
        session_id: Session this result belongs to
        source_language: ISO 639-1 language code (e.g., 'en', 'es')
    """
    
    result_id: str
    text: str
    stability_score: Optional[float]
    timestamp: float
    is_partial: bool = True
    session_id: str = ""
    source_language: str = ""
    
    def __post_init__(self):
        """Validate field constraints."""
        if not self.result_id:
            raise ValueError("result_id cannot be empty")
        
        if not self.text:
            raise ValueError("text cannot be empty")
        
        if self.stability_score is not None:
            if not 0.0 <= self.stability_score <= 1.0:
                raise ValueError(f"stability_score must be between 0.0 and 1.0, got {self.stability_score}")
        
        if self.timestamp <= 0:
            raise ValueError(f"timestamp must be positive, got {self.timestamp}")
        
        if self.source_language and len(self.source_language) != 2:
            raise ValueError(f"source_language must be 2-character ISO 639-1 code, got '{self.source_language}'")


@dataclass
class FinalResult:
    """
    Represents a final transcription result from AWS Transcribe.
    
    Final results are completed transcription segments that will not change.
    They replace any corresponding partial results.
    
    Attributes:
        result_id: Unique identifier for this result
        text: Transcribed text
        timestamp: Unix timestamp (seconds) when result was generated
        is_partial: Always False for final results
        session_id: Session this result belongs to
        source_language: ISO 639-1 language code (e.g., 'en', 'es')
        replaces_result_ids: List of partial result IDs this replaces
    """
    
    result_id: str
    text: str
    timestamp: float
    is_partial: bool = False
    session_id: str = ""
    source_language: str = ""
    replaces_result_ids: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate field constraints."""
        if not self.result_id:
            raise ValueError("result_id cannot be empty")
        
        if not self.text:
            raise ValueError("text cannot be empty")
        
        if self.timestamp <= 0:
            raise ValueError(f"timestamp must be positive, got {self.timestamp}")
        
        if self.source_language and len(self.source_language) != 2:
            raise ValueError(f"source_language must be 2-character ISO 639-1 code, got '{self.source_language}'")


@dataclass
class BufferedResult:
    """
    Represents a partial result stored in the buffer.
    
    Buffered results track additional metadata needed for processing,
    including when they were added to the buffer and whether they've
    been forwarded to translation.
    
    Attributes:
        result_id: Unique identifier for this result
        text: Transcribed text
        stability_score: Confidence metric (0.0-1.0), None if unavailable
        timestamp: Original event timestamp (Unix seconds)
        added_at: When added to buffer (Unix seconds)
        forwarded: Whether forwarded to translation pipeline
        session_id: Session this result belongs to
    """
    
    result_id: str
    text: str
    stability_score: Optional[float]
    timestamp: float
    added_at: float
    forwarded: bool = False
    session_id: str = ""
    
    def __post_init__(self):
        """Validate field constraints."""
        if not self.result_id:
            raise ValueError("result_id cannot be empty")
        
        if not self.text:
            raise ValueError("text cannot be empty")
        
        if self.stability_score is not None:
            if not 0.0 <= self.stability_score <= 1.0:
                raise ValueError(f"stability_score must be between 0.0 and 1.0, got {self.stability_score}")
        
        if self.timestamp <= 0:
            raise ValueError(f"timestamp must be positive, got {self.timestamp}")
        
        if self.added_at <= 0:
            raise ValueError(f"added_at must be positive, got {self.added_at}")


@dataclass
class ResultMetadata:
    """
    Metadata extracted from transcription event.
    
    This dataclass provides a structured representation of the key
    information extracted from AWS Transcribe events.
    
    Attributes:
        is_partial: Whether this is a partial or final result
        stability_score: Confidence metric (0.0-1.0), None if unavailable
        text: Transcribed text
        result_id: Unique identifier for this result
        timestamp: Unix timestamp (seconds) when result was generated
        alternatives: Alternative transcriptions (if available)
    """
    
    is_partial: bool
    stability_score: Optional[float]
    text: str
    result_id: str
    timestamp: float
    alternatives: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate field constraints."""
        if not self.result_id:
            raise ValueError("result_id cannot be empty")
        
        if not self.text:
            raise ValueError("text cannot be empty")
        
        if self.stability_score is not None:
            if not 0.0 <= self.stability_score <= 1.0:
                raise ValueError(f"stability_score must be between 0.0 and 1.0, got {self.stability_score}")
        
        if self.timestamp <= 0:
            raise ValueError(f"timestamp must be positive, got {self.timestamp}")
