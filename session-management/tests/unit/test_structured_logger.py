"""
Unit tests for structured logger factory function.

Tests the get_structured_logger factory function to ensure it creates
properly configured StructuredLogger instances with various parameter
combinations.
"""

import pytest
from shared.utils.structured_logger import (
    get_structured_logger,
    StructuredLogger
)


class TestGetStructuredLogger:
    """Test suite for get_structured_logger factory function."""
    
    def test_basic_instance_creation_with_component_name(self):
        """Test basic instance creation with only component name."""
        # Arrange
        component_name = 'TestComponent'
        
        # Act
        logger = get_structured_logger(component_name)
        
        # Assert
        assert isinstance(logger, StructuredLogger)
        assert logger.component == component_name
        assert logger.session_id is None
        assert logger.connection_id is None
        assert logger.request_id is None
    
    def test_with_optional_correlation_id_parameter(self):
        """Test instance creation with correlation_id parameter."""
        # Arrange
        component_name = 'TestComponent'
        correlation_id = 'corr-123'
        
        # Act
        logger = get_structured_logger(component_name, correlation_id=correlation_id)
        
        # Assert
        assert isinstance(logger, StructuredLogger)
        assert logger.component == component_name
        assert logger.request_id == correlation_id
    
    def test_with_optional_session_id_parameter(self):
        """Test instance creation with session_id parameter."""
        # Arrange
        component_name = 'TestComponent'
        session_id = 'golden-eagle-427'
        
        # Act
        logger = get_structured_logger(component_name, session_id=session_id)
        
        # Assert
        assert isinstance(logger, StructuredLogger)
        assert logger.component == component_name
        assert logger.session_id == session_id
    
    def test_with_optional_connection_id_parameter(self):
        """Test instance creation with connection_id parameter."""
        # Arrange
        component_name = 'TestComponent'
        connection_id = 'conn-abc123'
        
        # Act
        logger = get_structured_logger(component_name, connection_id=connection_id)
        
        # Assert
        assert isinstance(logger, StructuredLogger)
        assert logger.component == component_name
        assert logger.connection_id == connection_id
    
    def test_with_optional_request_id_parameter(self):
        """Test instance creation with request_id parameter."""
        # Arrange
        component_name = 'TestComponent'
        request_id = 'req-xyz789'
        
        # Act
        logger = get_structured_logger(component_name, request_id=request_id)
        
        # Assert
        assert isinstance(logger, StructuredLogger)
        assert logger.component == component_name
        assert logger.request_id == request_id
    
    def test_with_multiple_optional_parameters(self):
        """Test instance creation with multiple optional parameters."""
        # Arrange
        component_name = 'TestComponent'
        session_id = 'golden-eagle-427'
        connection_id = 'conn-abc123'
        request_id = 'req-xyz789'
        
        # Act
        logger = get_structured_logger(
            component_name,
            session_id=session_id,
            connection_id=connection_id,
            request_id=request_id
        )
        
        # Assert
        assert isinstance(logger, StructuredLogger)
        assert logger.component == component_name
        assert logger.session_id == session_id
        assert logger.connection_id == connection_id
        assert logger.request_id == request_id
    
    def test_correlation_id_maps_to_request_id(self):
        """Test that correlation_id parameter maps to request_id for backward compatibility."""
        # Arrange
        component_name = 'TestComponent'
        correlation_id = 'corr-123'
        
        # Act
        logger = get_structured_logger(component_name, correlation_id=correlation_id)
        
        # Assert
        assert logger.request_id == correlation_id
    
    def test_request_id_takes_precedence_over_correlation_id(self):
        """Test that request_id takes precedence when both are provided."""
        # Arrange
        component_name = 'TestComponent'
        correlation_id = 'corr-123'
        request_id = 'req-456'
        
        # Act
        logger = get_structured_logger(
            component_name,
            correlation_id=correlation_id,
            request_id=request_id
        )
        
        # Assert
        assert logger.request_id == request_id
    
    def test_backward_compatibility_with_direct_instantiation(self):
        """Test that factory function is compatible with direct StructuredLogger instantiation."""
        # Arrange
        component_name = 'TestComponent'
        session_id = 'golden-eagle-427'
        
        # Act - Create logger using factory
        factory_logger = get_structured_logger(component_name, session_id=session_id)
        
        # Act - Create logger using direct instantiation
        direct_logger = StructuredLogger(component=component_name, session_id=session_id)
        
        # Assert - Both should have same attributes
        assert factory_logger.component == direct_logger.component
        assert factory_logger.session_id == direct_logger.session_id
        assert factory_logger.connection_id == direct_logger.connection_id
        assert factory_logger.request_id == direct_logger.request_id
    
    def test_logger_can_log_messages(self):
        """Test that created logger can actually log messages."""
        # Arrange
        component_name = 'TestComponent'
        logger = get_structured_logger(component_name)
        
        # Act & Assert - Should not raise any exceptions
        logger.info('Test message')
        logger.debug('Debug message')
        logger.warning('Warning message')
        logger.error('Error message')
    
    def test_logger_with_all_parameters_can_log(self):
        """Test that logger with all parameters can log messages with context."""
        # Arrange
        logger = get_structured_logger(
            'TestComponent',
            session_id='golden-eagle-427',
            connection_id='conn-abc123',
            request_id='req-xyz789'
        )
        
        # Act & Assert - Should not raise any exceptions
        logger.info('Test message with full context', operation='test_operation')
