"""
Unit tests for Session ID Service.
"""

import pytest
from unittest.mock import Mock, patch
import time

from shared.utils.session_id_service import SessionIDService
from shared.data_access.sessions_repository import SessionsRepository


class TestSessionIDService:
    """Test cases for SessionIDService."""
    
    @pytest.fixture
    def mock_sessions_repository(self):
        """Create a mock sessions repository."""
        return Mock(spec=SessionsRepository)
    
    @pytest.fixture
    def service(self, mock_sessions_repository):
        """Create a SessionIDService with mocked repository."""
        return SessionIDService(
            sessions_repository=mock_sessions_repository,
            max_attempts=5,
            retry_base_delay=0.01  # Short delay for testing
        )
    
    def test_generate_unique_session_id_success(self, service, mock_sessions_repository):
        """Test successful generation of unique session ID."""
        # Mock repository to indicate ID is unique
        mock_sessions_repository.session_exists.return_value = False
        
        session_id = service.generate_unique_session_id()
        
        # Verify format
        assert SessionIDService.validate_session_id_format(session_id)
        
        # Verify repository was called
        mock_sessions_repository.session_exists.assert_called()
    
    def test_generate_with_collision_then_success(self, service, mock_sessions_repository):
        """Test generation with collision followed by success."""
        # Mock repository to fail first 2 times, then succeed
        call_count = 0
        def mock_exists(session_id):
            nonlocal call_count
            call_count += 1
            return call_count <= 2  # Exists for first 2 calls
        
        mock_sessions_repository.session_exists.side_effect = mock_exists
        
        session_id = service.generate_unique_session_id()
        
        # Should succeed after retries
        assert SessionIDService.validate_session_id_format(session_id)
        assert call_count >= 3  # Should have tried at least 3 times
    
    def test_generate_max_attempts_exceeded(self, service, mock_sessions_repository):
        """Test that max attempts limit is enforced."""
        # Mock repository to always indicate collision
        mock_sessions_repository.session_exists.return_value = True
        
        with pytest.raises(RuntimeError, match='Failed to generate unique session ID'):
            service.generate_unique_session_id()
    
    def test_exponential_backoff_on_collisions(self, service, mock_sessions_repository):
        """Test that exponential backoff is applied when generator exhausts attempts."""
        # Mock to always fail - this will cause generator to exhaust its attempts
        # and trigger service-level retry with backoff
        attempt_count = 0
        def mock_exists(session_id):
            nonlocal attempt_count
            attempt_count += 1
            # Fail for first service attempt (generator will try 5 times = 5 calls)
            # Succeed on second service attempt (next 5 calls)
            return attempt_count <= 5
        
        mock_sessions_repository.session_exists.side_effect = mock_exists
        
        start_time = time.time()
        session_id = service.generate_unique_session_id()
        elapsed_time = time.time() - start_time
        
        # Should have some delay due to backoff (at least 0.01s for first retry)
        assert elapsed_time >= 0.01, "Should have exponential backoff delay"
        assert SessionIDService.validate_session_id_format(session_id)
        # Should have made multiple attempts
        assert attempt_count > 5, "Should have retried after generator exhaustion"
    
    def test_validate_session_id_format_valid(self):
        """Test format validation for valid session IDs."""
        valid_ids = [
            'faithful-shepherd-123',
            'blessed-covenant-999',
            'gracious-temple-100'
        ]
        
        for session_id in valid_ids:
            assert SessionIDService.validate_session_id_format(session_id)
    
    def test_validate_session_id_format_invalid(self):
        """Test format validation for invalid session IDs."""
        invalid_ids = [
            '',
            'invalid',
            'faithful-shepherd',
            'faithful-shepherd-12',
            'faithful-shepherd-1234',
            'faithful-shepherd-abc'
        ]
        
        for session_id in invalid_ids:
            assert not SessionIDService.validate_session_id_format(session_id)
    
    def test_uniqueness_check_integration(self, service, mock_sessions_repository):
        """Test that uniqueness check properly integrates with repository."""
        # Setup mock to return specific values
        existing_ids = {'faithful-shepherd-123', 'blessed-covenant-456'}
        mock_sessions_repository.session_exists.side_effect = \
            lambda sid: sid in existing_ids
        
        # Generate should avoid existing IDs
        session_id = service.generate_unique_session_id()
        
        assert session_id not in existing_ids
        assert SessionIDService.validate_session_id_format(session_id)
    
    def test_logging_on_collisions(self, service, mock_sessions_repository, caplog):
        """Test that collisions are logged appropriately."""
        # Mock to exhaust generator attempts, triggering service-level retry
        call_count = 0
        def mock_exists(session_id):
            nonlocal call_count
            call_count += 1
            # Fail for first 5 attempts (generator exhausts), then succeed
            return call_count <= 5
        
        mock_sessions_repository.session_exists.side_effect = mock_exists
        
        with caplog.at_level('INFO'):
            session_id = service.generate_unique_session_id()
        
        # Should log generation success
        assert any('generated' in record.message.lower() for record in caplog.records)
    
    def test_multiple_generations_are_unique(self, service, mock_sessions_repository):
        """Test that multiple generations produce unique IDs."""
        generated_ids = set()
        
        def mock_exists(session_id):
            # Check against already generated IDs
            exists = session_id in generated_ids
            if not exists:
                generated_ids.add(session_id)
            return exists
        
        mock_sessions_repository.session_exists.side_effect = mock_exists
        
        # Generate multiple IDs
        ids = []
        for _ in range(10):
            session_id = service.generate_unique_session_id()
            ids.append(session_id)
        
        # All should be unique
        assert len(ids) == len(set(ids)), "All generated IDs should be unique"
