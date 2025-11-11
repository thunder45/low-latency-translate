"""
Configuration data model for partial result processing.

This module defines the configuration dataclass that controls all tunable
parameters for partial result processing, including stability thresholds,
timeouts, and rate limits.
"""

from dataclasses import dataclass


@dataclass
class PartialResultConfig:
    """
    Configuration for partial result processing.
    
    This dataclass encapsulates all tunable parameters that control how
    partial results are processed, buffered, and forwarded to translation.
    
    Attributes:
        enabled: Enable/disable partial result processing
        min_stability_threshold: Minimum stability score to forward (0.70-0.95)
        max_buffer_timeout_seconds: Maximum time to buffer results (2-10)
        pause_threshold_seconds: Pause duration to trigger sentence boundary (default: 2.0)
        orphan_timeout_seconds: Time before flushing orphaned results (default: 15.0)
        max_rate_per_second: Maximum partial results to process per second (default: 5)
        dedup_cache_ttl_seconds: Deduplication cache TTL (default: 10)
    """
    
    enabled: bool = True
    min_stability_threshold: float = 0.85
    max_buffer_timeout_seconds: float = 5.0
    pause_threshold_seconds: float = 2.0
    orphan_timeout_seconds: float = 15.0
    max_rate_per_second: int = 5
    dedup_cache_ttl_seconds: int = 10
    
    def validate(self) -> None:
        """
        Validate configuration parameters.
        
        Raises:
            ValueError: If any parameter is outside its valid range
        """
        if not 0.70 <= self.min_stability_threshold <= 0.95:
            raise ValueError(
                f"min_stability_threshold must be between 0.70 and 0.95, "
                f"got {self.min_stability_threshold}"
            )
        
        if not 2.0 <= self.max_buffer_timeout_seconds <= 10.0:
            raise ValueError(
                f"max_buffer_timeout_seconds must be between 2 and 10, "
                f"got {self.max_buffer_timeout_seconds}"
            )
        
        if self.pause_threshold_seconds < 0:
            raise ValueError(
                f"pause_threshold_seconds must be non-negative, "
                f"got {self.pause_threshold_seconds}"
            )
        
        if self.orphan_timeout_seconds < 0:
            raise ValueError(
                f"orphan_timeout_seconds must be non-negative, "
                f"got {self.orphan_timeout_seconds}"
            )
        
        if self.max_rate_per_second < 1:
            raise ValueError(
                f"max_rate_per_second must be at least 1, "
                f"got {self.max_rate_per_second}"
            )
        
        if self.dedup_cache_ttl_seconds < 1:
            raise ValueError(
                f"dedup_cache_ttl_seconds must be at least 1, "
                f"got {self.dedup_cache_ttl_seconds}"
            )
    
    def __post_init__(self):
        """Validate configuration on initialization."""
        self.validate()
