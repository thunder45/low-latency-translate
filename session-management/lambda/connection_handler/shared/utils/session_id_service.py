"""
Session ID Service

Integrates session ID generation with DynamoDB uniqueness validation.
"""

import logging
import time
from typing import Optional

from .session_id_generator import SessionIDGenerator
from ..data_access.sessions_repository import SessionsRepository

logger = logging.getLogger(__name__)


class SessionIDService:
    """
    Service for generating unique session IDs with DynamoDB validation.
    """
    
    def __init__(
        self,
        sessions_repository: SessionsRepository,
        max_attempts: int = 10,
        retry_base_delay: float = 0.1
    ):
        """
        Initialize the session ID service.
        
        Args:
            sessions_repository: Repository for checking session existence
            max_attempts: Maximum attempts to generate unique ID
            retry_base_delay: Base delay for exponential backoff (seconds)
        """
        self.sessions_repository = sessions_repository
        self.generator = SessionIDGenerator(max_attempts=max_attempts)
        self.retry_base_delay = retry_base_delay
        self.max_attempts = max_attempts
    
    def _check_uniqueness(self, session_id: str) -> bool:
        """
        Check if session ID is unique in DynamoDB.
        
        Args:
            session_id: Session ID to check
        
        Returns:
            True if session ID is unique (does not exist)
        """
        return not self.sessions_repository.session_exists(session_id)
    
    def generate_unique_session_id(self) -> str:
        """
        Generate a unique session ID with DynamoDB validation and retry logic.
        
        Returns:
            Unique session ID
        
        Raises:
            RuntimeError: If unable to generate unique ID after max attempts
        """
        collision_count = 0
        
        for attempt in range(self.max_attempts):
            try:
                # Generate session ID with uniqueness check
                session_id = self.generator.generate(
                    uniqueness_check=self._check_uniqueness
                )
                
                if collision_count > 0:
                    logger.info(
                        f"Successfully generated unique session ID '{session_id}' "
                        f"after {collision_count} collision(s)"
                    )
                
                return session_id
            
            except RuntimeError as e:
                # Generator exhausted its attempts due to collisions
                collision_count += 1
                
                if attempt == self.max_attempts - 1:
                    # Final attempt failed
                    error_msg = (
                        f"Failed to generate unique session ID after "
                        f"{self.max_attempts} attempts with {collision_count} collision(s)"
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                
                # Exponential backoff before retry
                delay = self.retry_base_delay * (2 ** attempt)
                logger.warning(
                    f"Session ID generation attempt {attempt + 1} failed "
                    f"with {collision_count} collision(s), "
                    f"retrying after {delay:.2f}s"
                )
                time.sleep(delay)
        
        # Should not reach here, but just in case
        raise RuntimeError(
            f"Failed to generate unique session ID after {self.max_attempts} attempts"
        )
    
    @staticmethod
    def validate_session_id_format(session_id: str) -> bool:
        """
        Validate session ID format.
        
        Args:
            session_id: Session ID to validate
        
        Returns:
            True if format is valid
        """
        return SessionIDGenerator.validate_format(session_id)
