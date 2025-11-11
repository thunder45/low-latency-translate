"""
Feature flag service for gradual rollout of partial results processing.

This service manages feature flags using AWS Systems Manager Parameter Store
to enable dynamic configuration without redeployment. Supports canary deployment
with percentage-based rollout (10% → 50% → 100%).
"""

import os
import hashlib
import logging
from typing import Optional
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class FeatureFlagConfig:
    """Configuration for partial results feature flag."""
    
    enabled: bool = True  # Global enable/disable
    rollout_percentage: int = 100  # Percentage of sessions to enable (0-100)
    min_stability_threshold: float = 0.85
    max_buffer_timeout: float = 5.0
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        if not 0 <= self.rollout_percentage <= 100:
            raise ValueError("rollout_percentage must be between 0 and 100")
        if not 0.70 <= self.min_stability_threshold <= 0.95:
            raise ValueError("min_stability_threshold must be between 0.70 and 0.95")
        if not 2.0 <= self.max_buffer_timeout <= 10.0:
            raise ValueError("max_buffer_timeout must be between 2 and 10")


class FeatureFlagService:
    """
    Service for managing feature flags with gradual rollout support.
    
    Uses AWS Systems Manager Parameter Store for dynamic configuration.
    Implements consistent hashing for stable session assignment during rollout.
    """
    
    def __init__(
        self,
        parameter_name: str = '/audio-transcription/partial-results/config',
        cache_ttl_seconds: int = 60
    ):
        """
        Initialize feature flag service.
        
        Args:
            parameter_name: SSM parameter name for configuration
            cache_ttl_seconds: How long to cache parameter value
        """
        self.parameter_name = parameter_name
        self.cache_ttl_seconds = cache_ttl_seconds
        self.ssm_client = boto3.client('ssm')
        
        # Cache for parameter value
        self._cached_config: Optional[FeatureFlagConfig] = None
        self._cache_timestamp: float = 0
        
        # Fallback to environment variables if SSM unavailable
        self._env_fallback_enabled = os.getenv('PARTIAL_RESULTS_ENABLED', 'true').lower() == 'true'
    
    def is_enabled_for_session(self, session_id: str) -> bool:
        """
        Check if partial results are enabled for a specific session.
        
        Uses consistent hashing to ensure same session always gets same result
        during gradual rollout. This prevents sessions from flipping between
        enabled/disabled states.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if partial results should be enabled for this session
        """
        try:
            config = self._get_config()
            
            # Check global enable flag
            if not config.enabled:
                logger.info(f"Partial results globally disabled for session {session_id}")
                return False
            
            # Check rollout percentage using consistent hashing
            if config.rollout_percentage < 100:
                session_hash = self._hash_session_id(session_id)
                session_bucket = session_hash % 100  # 0-99
                
                is_enabled = session_bucket < config.rollout_percentage
                logger.info(
                    f"Session {session_id} rollout check: "
                    f"bucket={session_bucket}, threshold={config.rollout_percentage}, "
                    f"enabled={is_enabled}"
                )
                return is_enabled
            
            # 100% rollout - enabled for all
            return True
            
        except Exception as e:
            logger.error(f"Error checking feature flag for session {session_id}: {e}")
            # Fallback to environment variable on error
            return self._env_fallback_enabled
    
    def get_config_for_session(self, session_id: str) -> FeatureFlagConfig:
        """
        Get feature flag configuration for a specific session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Feature flag configuration with enabled flag set based on rollout
        """
        config = self._get_config()
        
        # Override enabled flag based on session rollout
        config.enabled = self.is_enabled_for_session(session_id)
        
        return config
    
    def _get_config(self) -> FeatureFlagConfig:
        """
        Get feature flag configuration from Parameter Store with caching.
        
        Returns:
            Feature flag configuration
        """
        import time
        
        # Check cache
        current_time = time.time()
        if (self._cached_config is not None and 
            current_time - self._cache_timestamp < self.cache_ttl_seconds):
            return self._cached_config
        
        # Fetch from Parameter Store
        try:
            response = self.ssm_client.get_parameter(
                Name=self.parameter_name,
                WithDecryption=False
            )
            
            # Parse JSON configuration
            import json
            param_value = json.loads(response['Parameter']['Value'])
            
            config = FeatureFlagConfig(
                enabled=param_value.get('enabled', True),
                rollout_percentage=param_value.get('rollout_percentage', 100),
                min_stability_threshold=param_value.get('min_stability_threshold', 0.85),
                max_buffer_timeout=param_value.get('max_buffer_timeout', 5.0)
            )
            
            config.validate()
            
            # Update cache
            self._cached_config = config
            self._cache_timestamp = current_time
            
            logger.info(f"Loaded feature flag config from Parameter Store: {config}")
            return config
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                logger.warning(
                    f"Parameter {self.parameter_name} not found, using defaults"
                )
            else:
                logger.error(f"Error fetching parameter from SSM: {e}")
            
            # Return default configuration
            return self._get_default_config()
        
        except Exception as e:
            logger.error(f"Error parsing feature flag configuration: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> FeatureFlagConfig:
        """
        Get default configuration from environment variables.
        
        Returns:
            Default feature flag configuration
        """
        return FeatureFlagConfig(
            enabled=os.getenv('PARTIAL_RESULTS_ENABLED', 'true').lower() == 'true',
            rollout_percentage=int(os.getenv('ROLLOUT_PERCENTAGE', '100')),
            min_stability_threshold=float(os.getenv('MIN_STABILITY_THRESHOLD', '0.85')),
            max_buffer_timeout=float(os.getenv('MAX_BUFFER_TIMEOUT', '5.0'))
        )
    
    def _hash_session_id(self, session_id: str) -> int:
        """
        Generate consistent hash for session ID.
        
        Uses SHA-256 to ensure uniform distribution across 0-99 buckets.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Hash value as integer
        """
        hash_bytes = hashlib.sha256(session_id.encode()).digest()
        # Use first 4 bytes as integer
        return int.from_bytes(hash_bytes[:4], byteorder='big')
    
    def invalidate_cache(self) -> None:
        """Invalidate cached configuration to force refresh."""
        self._cached_config = None
        self._cache_timestamp = 0
        logger.info("Feature flag cache invalidated")
