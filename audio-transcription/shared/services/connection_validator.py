"""
Connection and session validation service for audio processor.

This module provides validation logic for WebSocket connections and sessions,
ensuring that only authorized speakers can send audio and that sessions are active.
"""

import logging
import os
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Base exception for validation errors."""
    pass


class UnauthorizedError(ValidationError):
    """Raised when connection is not authorized (403)."""
    pass


class SessionNotFoundError(ValidationError):
    """Raised when session is not found (404)."""
    pass


class SessionInactiveError(ValidationError):
    """Raised when session is inactive (410)."""
    pass


@dataclass
class ValidationResult:
    """
    Result of connection and session validation.
    
    Attributes:
        connection_id: WebSocket connection ID
        session_id: Session identifier
        source_language: Source language code
        role: Connection role (speaker or listener)
        is_valid: Whether validation passed
    """
    connection_id: str
    session_id: str
    source_language: str
    role: str
    is_valid: bool = True


class ConnectionValidator:
    """
    Validator for WebSocket connections and sessions.
    
    This class validates that:
    1. Connection exists in Connections table
    2. Connection role is 'speaker'
    3. Session exists in Sessions table
    4. Session is active (isActive=true)
    
    Examples:
        >>> validator = ConnectionValidator(connections_repo, sessions_repo)
        >>> result = validator.validate_connection_and_session(connection_id)
    """
    
    def __init__(self, connections_repository, sessions_repository):
        """
        Initialize connection validator.
        
        Args:
            connections_repository: Repository for Connections table
            sessions_repository: Repository for Sessions table
        """
        self.connections_repo = connections_repository
        self.sessions_repo = sessions_repository
        
        logger.info("Initialized ConnectionValidator")
    
    def validate_connection_and_session(
        self,
        connection_id: str
    ) -> ValidationResult:
        """
        Validate connection and associated session.
        
        Performs the following checks:
        1. Query Connections table using connectionId
        2. Verify role=speaker
        3. Extract sessionId from connection record
        4. Query Sessions table to verify isActive=true
        
        Args:
            connection_id: WebSocket connection ID
        
        Returns:
            ValidationResult with connection and session details
        
        Raises:
            UnauthorizedError: If connection not found or role != speaker (403)
            SessionNotFoundError: If session not found (404)
            SessionInactiveError: If session is inactive (410)
        
        Examples:
            >>> result = validator.validate_connection_and_session('conn-123')
            >>> assert result.role == 'speaker'
            >>> assert result.is_valid == True
        """
        try:
            # Step 1: Query Connections table
            connection = self.connections_repo.get_connection(connection_id)
            
            if not connection:
                logger.warning(
                    f"Connection not found: {connection_id}"
                )
                raise UnauthorizedError(
                    f"Connection not found or unauthorized: {connection_id}"
                )
            
            # Step 2: Verify role=speaker
            role = connection.get('role', '')
            if role != 'speaker':
                logger.warning(
                    f"Connection {connection_id} has invalid role: {role}. "
                    f"Only speakers can send audio."
                )
                raise UnauthorizedError(
                    f"Only speakers can send audio. Current role: {role}"
                )
            
            # Step 3: Extract sessionId
            session_id = connection.get('sessionId')
            if not session_id:
                logger.error(
                    f"Connection {connection_id} missing sessionId"
                )
                raise UnauthorizedError(
                    f"Connection missing session information"
                )
            
            # Step 4: Query Sessions table
            session = self.sessions_repo.get_session(session_id)
            
            if not session:
                logger.warning(
                    f"Session not found: {session_id} for connection {connection_id}"
                )
                raise SessionNotFoundError(
                    f"Session not found: {session_id}"
                )
            
            # Step 5: Verify session is active
            is_active = session.get('isActive', False)
            if not is_active:
                logger.warning(
                    f"Session {session_id} is inactive"
                )
                raise SessionInactiveError(
                    f"Session {session_id} is no longer active"
                )
            
            # Extract source language
            source_language = session.get('sourceLanguage', 'en')
            
            logger.info(
                f"Validation successful: connection={connection_id}, "
                f"session={session_id}, role={role}, language={source_language}"
            )
            
            return ValidationResult(
                connection_id=connection_id,
                session_id=session_id,
                source_language=source_language,
                role=role,
                is_valid=True
            )
            
        except (UnauthorizedError, SessionNotFoundError, SessionInactiveError):
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during validation: {e}",
                exc_info=True
            )
            raise ValidationError(f"Validation failed: {e}")
    
    def is_speaker_connection(self, connection_id: str) -> bool:
        """
        Quick check if connection is a speaker.
        
        Args:
            connection_id: WebSocket connection ID
        
        Returns:
            True if connection exists and role is speaker, False otherwise
        """
        try:
            connection = self.connections_repo.get_connection(connection_id)
            if not connection:
                return False
            
            role = connection.get('role', '')
            return role == 'speaker'
            
        except Exception as e:
            logger.error(f"Error checking speaker connection: {e}")
            return False
    
    def get_session_for_connection(
        self,
        connection_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get session associated with connection.
        
        Args:
            connection_id: WebSocket connection ID
        
        Returns:
            Session dict or None if not found
        """
        try:
            connection = self.connections_repo.get_connection(connection_id)
            if not connection:
                return None
            
            session_id = connection.get('sessionId')
            if not session_id:
                return None
            
            return self.sessions_repo.get_session(session_id)
            
        except Exception as e:
            logger.error(f"Error getting session for connection: {e}")
            return None


def create_validator_from_env():
    """
    Create ConnectionValidator from environment variables.
    
    Reads table names from environment and creates repositories.
    
    Environment variables:
    - CONNECTIONS_TABLE_NAME: Name of Connections table
    - SESSIONS_TABLE_NAME: Name of Sessions table
    
    Returns:
        ConnectionValidator instance
    
    Raises:
        ValueError: If required environment variables are missing
    """
    # Import here to avoid circular dependencies
    import sys
    import os
    
    # Add session-management to path to import repositories
    session_mgmt_path = os.path.join(
        os.path.dirname(__file__),
        '../../../session-management'
    )
    if os.path.exists(session_mgmt_path):
        sys.path.insert(0, session_mgmt_path)
    
    try:
        from shared.data_access.connections_repository import ConnectionsRepository
        from shared.data_access.sessions_repository import SessionsRepository
    except ImportError as e:
        logger.error(f"Failed to import repositories: {e}")
        raise ValueError(f"Failed to import repositories: {e}")
    
    # Get table names from shared config
    try:
        from shared.config.table_names import get_table_name, SESSIONS_TABLE_NAME, CONNECTIONS_TABLE_NAME
        
        connections_table = get_table_name('CONNECTIONS_TABLE_NAME', CONNECTIONS_TABLE_NAME)
        sessions_table = get_table_name('SESSIONS_TABLE_NAME', SESSIONS_TABLE_NAME)
    except ImportError:
        # Fallback to environment variables if config not available
        connections_table = os.getenv('CONNECTIONS_TABLE_NAME', 'Connections')
        sessions_table = os.getenv('SESSIONS_TABLE_NAME', 'Sessions')
    
    # Create repositories
    connections_repo = ConnectionsRepository(connections_table)
    sessions_repo = SessionsRepository(sessions_table)
    
    # Create validator
    validator = ConnectionValidator(connections_repo, sessions_repo)
    
    logger.info(
        f"Created validator from environment: "
        f"connections_table={connections_table}, "
        f"sessions_table={sessions_table}"
    )
    
    return validator
