"""
Unit tests for TranscriptionEventHandler.

Tests event parsing, metadata extraction, routing logic, and error handling
for AWS Transcribe transcription events.
"""

import pytest
import time
from unittest.mock import Mock, MagicMock
from shared.services.transcription_event_handler import TranscriptionEventHandler
from shared.models.transcription_results import PartialResult, FinalResult


class TestTranscriptionEventHandler:
    """Test suite for TranscriptionEventHandler."""
    
    @pytest.fixture
    def mock_partial_handler(self):
        """Create mock partial result handler."""
        return Mock()
    
    @pytest.fixture
    def mock_final_handler(self):
        """Create mock final result handler."""
        return Mock()
    
    @pytest.fixture
    def handler(self, mock_partial_handler, mock_final_handler):
        """Create TranscriptionEventHandler instance."""
        return TranscriptionEventHandler(
            partial_handler=mock_partial_handler,
            final_handler=mock_final_handler,
            session_id="test-session-123",
            source_language="en"
        )
    
    @pytest.fixture
    def valid_partial_event_with_stability(self):
        """Create valid partial result event with stability score."""
        return {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123',
                    'StartTime': 1.5,
                    'EndTime': 2.5,
                    'Alternatives': [{
                        'Transcript': 'hello everyone',
                        'Items': [
                            {'Stability': 0.92, 'Content': 'hello'},
                            {'Stability': 0.89, 'Content': 'everyone'}
                        ]
                    }]
                }]
            }
        }
    
    @pytest.fixture
    def valid_partial_event_without_stability(self):
        """Create valid partial result event without stability scores."""
        return {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-456',
                    'Alternatives': [{
                        'Transcript': 'bonjour tout le monde',
                        'Items': []  # Empty items array
                    }]
                }]
            }
        }
    
    @pytest.fixture
    def valid_final_event(self):
        """Create valid final result event."""
        return {
            'Transcript': {
                'Results': [{
                    'IsPartial': False,
                    'ResultId': 'result-789',
                    'StartTime': 3.0,
                    'EndTime': 4.5,
                    'Alternatives': [{
                        'Transcript': 'this is the final result',
                        'Items': [
                            {'Content': 'this'},
                            {'Content': 'is'},
                            {'Content': 'the'},
                            {'Content': 'final'},
                            {'Content': 'result'}
                        ]
                    }]
                }]
            }
        }
    
    # Test: Event parsing with valid partial result and stability score
    def test_handle_event_with_partial_result_and_stability(
        self,
        handler,
        mock_partial_handler,
        valid_partial_event_with_stability
    ):
        """Test handling partial result event with stability score."""
        # Act
        handler.handle_event(valid_partial_event_with_stability)
        
        # Assert
        mock_partial_handler.process.assert_called_once()
        
        # Verify the PartialResult passed to handler
        call_args = mock_partial_handler.process.call_args[0]
        partial_result = call_args[0]
        
        assert isinstance(partial_result, PartialResult)
        assert partial_result.result_id == 'result-123'
        assert partial_result.text == 'hello everyone'
        assert partial_result.stability_score == 0.92
        assert partial_result.is_partial is True
        assert partial_result.session_id == 'test-session-123'
        assert partial_result.source_language == 'en'
    
    # Test: Event parsing with partial result without stability score
    def test_handle_event_with_partial_result_without_stability(
        self,
        handler,
        mock_partial_handler,
        valid_partial_event_without_stability
    ):
        """Test handling partial result event without stability scores."""
        # Act
        handler.handle_event(valid_partial_event_without_stability)
        
        # Assert
        mock_partial_handler.process.assert_called_once()
        
        # Verify the PartialResult has None stability
        call_args = mock_partial_handler.process.call_args[0]
        partial_result = call_args[0]
        
        assert isinstance(partial_result, PartialResult)
        assert partial_result.result_id == 'result-456'
        assert partial_result.text == 'bonjour tout le monde'
        assert partial_result.stability_score is None
        assert partial_result.is_partial is True
    
    # Test: Event parsing with final result
    def test_handle_event_with_final_result(
        self,
        handler,
        mock_final_handler,
        valid_final_event
    ):
        """Test handling final result event."""
        # Act
        handler.handle_event(valid_final_event)
        
        # Assert
        mock_final_handler.process.assert_called_once()
        
        # Verify the FinalResult passed to handler
        call_args = mock_final_handler.process.call_args[0]
        final_result = call_args[0]
        
        assert isinstance(final_result, FinalResult)
        assert final_result.result_id == 'result-789'
        assert final_result.text == 'this is the final result'
        assert final_result.is_partial is False
        assert final_result.session_id == 'test-session-123'
        assert final_result.source_language == 'en'
    
    # Test: Routing logic - partial vs final
    def test_routing_logic_partial_vs_final(
        self,
        handler,
        mock_partial_handler,
        mock_final_handler,
        valid_partial_event_with_stability,
        valid_final_event
    ):
        """Test that events are routed to correct handlers."""
        # Act - handle partial
        handler.handle_event(valid_partial_event_with_stability)
        
        # Assert - only partial handler called
        assert mock_partial_handler.process.call_count == 1
        assert mock_final_handler.process.call_count == 0
        
        # Reset mocks
        mock_partial_handler.reset_mock()
        mock_final_handler.reset_mock()
        
        # Act - handle final
        handler.handle_event(valid_final_event)
        
        # Assert - only final handler called
        assert mock_partial_handler.process.call_count == 0
        assert mock_final_handler.process.call_count == 1
    
    # Test: Malformed event - missing Transcript field
    def test_handle_event_with_missing_transcript_field(
        self,
        handler,
        mock_partial_handler,
        mock_final_handler
    ):
        """Test handling event with missing Transcript field."""
        # Arrange
        malformed_event = {'SomeOtherField': 'value'}
        
        # Act
        handler.handle_event(malformed_event)
        
        # Assert - no handlers called (error logged)
        mock_partial_handler.process.assert_not_called()
        mock_final_handler.process.assert_not_called()
    
    # Test: Malformed event - missing Results field
    def test_handle_event_with_missing_results_field(
        self,
        handler,
        mock_partial_handler,
        mock_final_handler
    ):
        """Test handling event with missing Results field."""
        # Arrange
        malformed_event = {
            'Transcript': {}
        }
        
        # Act
        handler.handle_event(malformed_event)
        
        # Assert - no handlers called
        mock_partial_handler.process.assert_not_called()
        mock_final_handler.process.assert_not_called()
    
    # Test: Malformed event - empty Results array
    def test_handle_event_with_empty_results_array(
        self,
        handler,
        mock_partial_handler,
        mock_final_handler
    ):
        """Test handling event with empty Results array."""
        # Arrange
        malformed_event = {
            'Transcript': {
                'Results': []
            }
        }
        
        # Act
        handler.handle_event(malformed_event)
        
        # Assert - no handlers called
        mock_partial_handler.process.assert_not_called()
        mock_final_handler.process.assert_not_called()
    
    # Test: Malformed event - missing IsPartial field
    def test_handle_event_with_missing_is_partial_field(
        self,
        handler,
        mock_partial_handler,
        mock_final_handler
    ):
        """Test handling event with missing IsPartial field."""
        # Arrange
        malformed_event = {
            'Transcript': {
                'Results': [{
                    'ResultId': 'result-123',
                    'Alternatives': [{
                        'Transcript': 'hello'
                    }]
                }]
            }
        }
        
        # Act
        handler.handle_event(malformed_event)
        
        # Assert - no handlers called
        mock_partial_handler.process.assert_not_called()
        mock_final_handler.process.assert_not_called()
    
    # Test: Malformed event - missing ResultId field
    def test_handle_event_with_missing_result_id_field(
        self,
        handler,
        mock_partial_handler,
        mock_final_handler
    ):
        """Test handling event with missing ResultId field."""
        # Arrange
        malformed_event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'Alternatives': [{
                        'Transcript': 'hello'
                    }]
                }]
            }
        }
        
        # Act
        handler.handle_event(malformed_event)
        
        # Assert - no handlers called
        mock_partial_handler.process.assert_not_called()
        mock_final_handler.process.assert_not_called()
    
    # Test: Malformed event - missing Alternatives field
    def test_handle_event_with_missing_alternatives_field(
        self,
        handler,
        mock_partial_handler,
        mock_final_handler
    ):
        """Test handling event with missing Alternatives field."""
        # Arrange
        malformed_event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123'
                }]
            }
        }
        
        # Act
        handler.handle_event(malformed_event)
        
        # Assert - no handlers called
        mock_partial_handler.process.assert_not_called()
        mock_final_handler.process.assert_not_called()
    
    # Test: Malformed event - empty Alternatives array
    def test_handle_event_with_empty_alternatives_array(
        self,
        handler,
        mock_partial_handler,
        mock_final_handler
    ):
        """Test handling event with empty Alternatives array."""
        # Arrange
        malformed_event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123',
                    'Alternatives': []
                }]
            }
        }
        
        # Act
        handler.handle_event(malformed_event)
        
        # Assert - no handlers called
        mock_partial_handler.process.assert_not_called()
        mock_final_handler.process.assert_not_called()
    
    # Test: Malformed event - missing Transcript in alternative
    def test_handle_event_with_missing_transcript_in_alternative(
        self,
        handler,
        mock_partial_handler,
        mock_final_handler
    ):
        """Test handling event with missing Transcript in alternative."""
        # Arrange
        malformed_event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123',
                    'Alternatives': [{
                        'Items': []
                    }]
                }]
            }
        }
        
        # Act
        handler.handle_event(malformed_event)
        
        # Assert - no handlers called
        mock_partial_handler.process.assert_not_called()
        mock_final_handler.process.assert_not_called()
    
    # Test: Malformed event - empty transcript text
    def test_handle_event_with_empty_transcript_text(
        self,
        handler,
        mock_partial_handler,
        mock_final_handler
    ):
        """Test handling event with empty transcript text."""
        # Arrange
        malformed_event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123',
                    'Alternatives': [{
                        'Transcript': '',
                        'Items': []
                    }]
                }]
            }
        }
        
        # Act
        handler.handle_event(malformed_event)
        
        # Assert - no handlers called
        mock_partial_handler.process.assert_not_called()
        mock_final_handler.process.assert_not_called()
    
    # Test: Null safety for Items array - None
    def test_null_safety_items_array_none(
        self,
        handler,
        mock_partial_handler
    ):
        """Test null safety when Items field is None."""
        # Arrange
        event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123',
                    'Alternatives': [{
                        'Transcript': 'hello world',
                        'Items': None
                    }]
                }]
            }
        }
        
        # Act
        handler.handle_event(event)
        
        # Assert - handler called with None stability
        mock_partial_handler.process.assert_called_once()
        call_args = mock_partial_handler.process.call_args[0]
        partial_result = call_args[0]
        assert partial_result.stability_score is None
    
    # Test: Null safety for Items array - missing Stability field
    def test_null_safety_items_missing_stability_field(
        self,
        handler,
        mock_partial_handler
    ):
        """Test null safety when Items exist but Stability field is missing."""
        # Arrange
        event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123',
                    'Alternatives': [{
                        'Transcript': 'hello world',
                        'Items': [
                            {'Content': 'hello'},
                            {'Content': 'world'}
                        ]
                    }]
                }]
            }
        }
        
        # Act
        handler.handle_event(event)
        
        # Assert - handler called with None stability
        mock_partial_handler.process.assert_called_once()
        call_args = mock_partial_handler.process.call_args[0]
        partial_result = call_args[0]
        assert partial_result.stability_score is None
    
    # Test: Null safety for Items array - invalid stability type
    def test_null_safety_items_invalid_stability_type(
        self,
        handler,
        mock_partial_handler
    ):
        """Test null safety when Stability field has invalid type."""
        # Arrange
        event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123',
                    'Alternatives': [{
                        'Transcript': 'hello world',
                        'Items': [
                            {'Stability': 'invalid', 'Content': 'hello'}
                        ]
                    }]
                }]
            }
        }
        
        # Act
        handler.handle_event(event)
        
        # Assert - handler called with None stability
        mock_partial_handler.process.assert_called_once()
        call_args = mock_partial_handler.process.call_args[0]
        partial_result = call_args[0]
        assert partial_result.stability_score is None
    
    # Test: Null safety for Items array - invalid stability value
    def test_null_safety_items_invalid_stability_value(
        self,
        handler,
        mock_partial_handler
    ):
        """Test null safety when Stability value is out of range."""
        # Arrange
        event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123',
                    'Alternatives': [{
                        'Transcript': 'hello world',
                        'Items': [
                            {'Stability': 1.5, 'Content': 'hello'}
                        ]
                    }]
                }]
            }
        }
        
        # Act
        handler.handle_event(event)
        
        # Assert - handler called with None stability
        mock_partial_handler.process.assert_called_once()
        call_args = mock_partial_handler.process.call_args[0]
        partial_result = call_args[0]
        assert partial_result.stability_score is None
    
    # Test: Metadata extraction with multiple alternatives
    def test_metadata_extraction_with_multiple_alternatives(
        self,
        handler,
        mock_partial_handler
    ):
        """Test that alternative transcriptions are extracted."""
        # Arrange
        event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123',
                    'Alternatives': [
                        {
                            'Transcript': 'hello everyone',
                            'Items': [{'Stability': 0.92}]
                        },
                        {
                            'Transcript': 'hello every one'
                        },
                        {
                            'Transcript': 'halo everyone'
                        }
                    ]
                }]
            }
        }
        
        # Act
        handler.handle_event(event)
        
        # Assert - handler called
        mock_partial_handler.process.assert_called_once()
        
        # Note: alternatives are extracted in _extract_result_metadata
        # but not passed to PartialResult (not in dataclass)
        # This test verifies the extraction doesn't cause errors
    
    # Test: Timestamp extraction from StartTime
    def test_timestamp_extraction_from_start_time(
        self,
        handler,
        mock_partial_handler
    ):
        """Test that timestamp is extracted from StartTime field."""
        # Arrange
        event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123',
                    'StartTime': 5.5,
                    'Alternatives': [{
                        'Transcript': 'hello world',
                        'Items': [{'Stability': 0.92}]
                    }]
                }]
            }
        }
        
        # Act
        handler.handle_event(event)
        
        # Assert
        mock_partial_handler.process.assert_called_once()
        call_args = mock_partial_handler.process.call_args[0]
        partial_result = call_args[0]
        assert partial_result.timestamp == 5.5
    
    # Test: Timestamp defaults to current time if missing
    def test_timestamp_defaults_to_current_time_if_missing(
        self,
        handler,
        mock_partial_handler
    ):
        """Test that timestamp defaults to current time if StartTime missing."""
        # Arrange
        event = {
            'Transcript': {
                'Results': [{
                    'IsPartial': True,
                    'ResultId': 'result-123',
                    'Alternatives': [{
                        'Transcript': 'hello world',
                        'Items': [{'Stability': 0.92}]
                    }]
                }]
            }
        }
        
        # Act
        before_time = time.time()
        handler.handle_event(event)
        after_time = time.time()
        
        # Assert
        mock_partial_handler.process.assert_called_once()
        call_args = mock_partial_handler.process.call_args[0]
        partial_result = call_args[0]
        
        # Timestamp should be between before and after
        assert before_time <= partial_result.timestamp <= after_time
