"""
Unit tests for connection validator.
"""

import pytest
from unittest.mock import Mock, MagicMock
from shared.services.connection_validator import (
    ConnectionValidator,
    ValidationResult,
    ValidationError,
    UnauthorizedError,
    SessionNotFoundError,
    SessionInactiveError
)


class TestConnectionValidator:
    """Test suite for ConnectionValidator."""
    
    @pytest.fixture
    def mock_connections_repo(self):
        """Create mock connections repository."""
        return Mock()
    
    @pytest.fixture
    def mock_sessions_repo(self):
        """Create mock sessions repository."""
        return Mock()
    
    @pytest.fixture
    def validator(self, mock_connections_repo, mock_sessions_repo):
        """Create validator with mock repositories."""
        return ConnectionValidator(mock_connections_repo, mock_sessions_repo)
    
    def test_validator_initialization(self, mock_connections_repo, mock_sessions_repo):
        """Test validator initializes correctly."""
        validator = ConnectionValidator(mock_connections_repo, mock_sessions_repo)
        
        assert validator.connections_repo == mock_connections_repo
        assert validator.sessions_repo == mock_sessions_repo
    
    def test_validate_connection_and_session_success(
        self,
        validator,
        mock_connections_repo,
        mock_sessions_repo
    ):
        """Test successful validation with valid speaker connection and active session."""
        # Setup mocks
        mock_connections_repo.get_connection.return_value = {
            'connectionId': 'conn-123',
            'sessionId': 'session-456',
            'role': 'speaker'
        }
        
        mock_sessions_repo.get_session.return_value = {
            'sessionId': 'session-456',
            'isActive': True,
            'sourceLanguage': 'en'
        }
        
        # Validate
        result = validator.validate_connection_and_session('conn-123')
        
        # Assertions
        assert isinstance(result, ValidationResult)
        assert result.connection_id == 'conn-123'
        assert result.session_id == 'session-456'
        assert result.source_language == 'en'
        assert result.role == 'speaker'
        assert result.is_valid is True
        
        # Verify repository calls
        mock_connections_repo.get_connection.assert_called_once_with('conn-123')
        mock_sessions_repo.get_session.assert_called_once_with('session-456')
    
    def test_validate_connection_not_found(
        self,
        validator,
        mock_connections_repo
    ):
        """Test validation fails when connection not found."""
        mock_connections_repo.get_connection.return_value = None
        
        with pytest.raises(UnauthorizedError, match="Connection not found"):
            validator.validate_connection_and_session('conn-999')
    
    def test_validate_connection_invalid_role(
        self,
        validator,
        mock_connections_repo
    ):
        """Test validation fails when connection role is not speaker."""
        mock_connections_repo.get_connection.return_value = {
            'connectionId': 'conn-123',
            'sessionId': 'session-456',
            'role': 'listener'
        }
        
        with pytest.raises(UnauthorizedError, match="Only speakers can send audio"):
            validator.validate_connection_and_session('conn-123')
    
    def test_validate_connection_missing_session_id(
        self,
        validator,
        mock_connections_repo
    ):
        """Test validation fails when connection missing sessionId."""
        mock_connections_repo.get_connection.return_value = {
            'connectionId': 'conn-123',
            'role': 'speaker'
            # Missing sessionId
        }
        
        with pytest.raises(UnauthorizedError, match="missing session information"):
            validator.validate_connection_and_session('conn-123')
    
    def test_validate_session_not_found(
        self,
        validator,
        mock_connections_repo,
        mock_sessions_repo
    ):
        """Test validation fails when session not found."""
        mock_connections_repo.get_connection.return_value = {
            'connectionId': 'conn-123',
            'sessionId': 'session-999',
            'role': 'speaker'
        }
        
        mock_sessions_repo.get_session.return_value = None
        
        with pytest.raises(SessionNotFoundError, match="Session not found"):
            validator.validate_connection_and_session('conn-123')
    
    def test_validate_session_inactive(
        self,
        validator,
        mock_connections_repo,
        mock_sessions_repo
    ):
        """Test validation fails when session is inactive."""
        mock_connections_repo.get_connection.return_value = {
            'connectionId': 'conn-123',
            'sessionId': 'session-456',
            'role': 'speaker'
        }
        
        mock_sessions_repo.get_session.return_value = {
            'sessionId': 'session-456',
            'isActive': False,
            'sourceLanguage': 'en'
        }
        
        with pytest.raises(SessionInactiveError, match="no longer active"):
            validator.validate_connection_and_session('conn-123')
    
    def test_validate_with_default_language(
        self,
        validator,
        mock_connections_repo,
        mock_sessions_repo
    ):
        """Test validation uses default language when not specified."""
        mock_connections_repo.get_connection.return_value = {
            'connectionId': 'conn-123',
            'sessionId': 'session-456',
            'role': 'speaker'
        }
        
        mock_sessions_repo.get_session.return_value = {
            'sessionId': 'session-456',
            'isActive': True
            # Missing sourceLanguage
        }
        
        result = validator.validate_connection_and_session('conn-123')
        
        assert result.source_language == 'en'  # Default
    
    def test_validate_unexpected_error(
        self,
        validator,
        mock_connections_repo
    ):
        """Test validation handles unexpected errors."""
        mock_connections_repo.get_connection.side_effect = Exception("Database error")
        
        with pytest.raises(ValidationError, match="Validation failed"):
            validator.validate_connection_and_session('conn-123')
    
    def test_is_speaker_connection_true(
        self,
        validator,
        mock_connections_repo
    ):
        """Test is_speaker_connection returns True for speaker."""
        mock_connections_repo.get_connection.return_value = {
            'connectionId': 'conn-123',
            'role': 'speaker'
        }
        
        result = validator.is_speaker_connection('conn-123')
        
        assert result is True
    
    def test_is_speaker_connection_false_listener(
        self,
        validator,
        mock_connections_repo
    ):
        """Test is_speaker_connection returns False for listener."""
        mock_connections_repo.get_connection.return_value = {
            'connectionId': 'conn-123',
            'role': 'listener'
        }
        
        result = validator.is_speaker_connection('conn-123')
        
        assert result is False
    
    def test_is_speaker_connection_false_not_found(
        self,
        validator,
        mock_connections_repo
    ):
        """Test is_speaker_connection returns False when connection not found."""
        mock_connections_repo.get_connection.return_value = None
        
        result = validator.is_speaker_connection('conn-999')
        
        assert result is False
    
    def test_is_speaker_connection_handles_error(
        self,
        validator,
        mock_connections_repo
    ):
        """Test is_speaker_connection handles errors gracefully."""
        mock_connections_repo.get_connection.side_effect = Exception("Error")
        
        result = validator.is_speaker_connection('conn-123')
        
        assert result is False
    
    def test_get_session_for_connection_success(
        self,
        validator,
        mock_connections_repo,
        mock_sessions_repo
    ):
        """Test getting session for connection."""
        mock_connections_repo.get_connection.return_value = {
            'connectionId': 'conn-123',
            'sessionId': 'session-456'
        }
        
        mock_sessions_repo.get_session.return_value = {
            'sessionId': 'session-456',
            'isActive': True
        }
        
        session = validator.get_session_for_connection('conn-123')
        
        assert session is not None
        assert session['sessionId'] == 'session-456'
    
    def test_get_session_for_connection_not_found(
        self,
        validator,
        mock_connections_repo
    ):
        """Test getting session returns None when connection not found."""
        mock_connections_repo.get_connection.return_value = None
        
        session = validator.get_session_for_connection('conn-999')
        
        assert session is None
    
    def test_get_session_for_connection_missing_session_id(
        self,
        validator,
        mock_connections_repo
    ):
        """Test getting session returns None when sessionId missing."""
        mock_connections_repo.get_connection.return_value = {
            'connectionId': 'conn-123'
            # Missing sessionId
        }
        
        session = validator.get_session_for_connection('conn-123')
        
        assert session is None
    
    def test_get_session_for_connection_handles_error(
        self,
        validator,
        mock_connections_repo
    ):
        """Test getting session handles errors gracefully."""
        mock_connections_repo.get_connection.side_effect = Exception("Error")
        
        session = validator.get_session_for_connection('conn-123')
        
        assert session is None
