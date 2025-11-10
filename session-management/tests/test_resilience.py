"""
Tests for resilience utilities (retry, circuit breaker, graceful degradation).
"""

import time
import pytest
from unittest.mock import Mock, patch

from shared.data_access.exceptions import RetryableError
from shared.utils.retry import retry_with_backoff, retry_operation
from shared.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    circuit_breaker
)
from shared.utils.graceful_degradation import (
    with_fallback,
    handle_dynamodb_unavailable,
    handle_cognito_unavailable,
    GracefulDegradationManager,
    degradation_manager,
    get_system_health
)


class TestRetryLogic:
    """Test retry logic with exponential backoff."""
    
    def test_retry_succeeds_on_first_attempt(self):
        """Test that successful operation doesn't retry."""
        mock_operation = Mock(return_value='success')
        
        @retry_with_backoff(max_retries=3, base_delay=0.1)
        def operation():
            return mock_operation()
        
        result = operation()
        
        assert result == 'success'
        assert mock_operation.call_count == 1
    
    def test_retry_succeeds_after_transient_errors(self):
        """Test retry logic with transient DynamoDB errors."""
        mock_operation = Mock(
            side_effect=[
                RetryableError("Transient error 1"),
                RetryableError("Transient error 2"),
                'success'
            ]
        )
        
        @retry_with_backoff(max_retries=3, base_delay=0.1)
        def operation():
            return mock_operation()
        
        result = operation()
        
        assert result == 'success'
        assert mock_operation.call_count == 3
    
    def test_retry_fails_after_max_retries(self):
        """Test that retry fails after max attempts."""
        mock_operation = Mock(side_effect=RetryableError("Persistent error"))
        
        @retry_with_backoff(max_retries=3, base_delay=0.1)
        def operation():
            return mock_operation()
        
        with pytest.raises(RetryableError, match="Persistent error"):
            operation()
        
        assert mock_operation.call_count == 4  # Initial + 3 retries
    
    def test_exponential_backoff_behavior(self):
        """Test exponential backoff timing."""
        call_times = []
        
        def failing_operation():
            call_times.append(time.time())
            raise RetryableError("Error")
        
        @retry_with_backoff(max_retries=3, base_delay=0.1, jitter=False)
        def operation():
            return failing_operation()
        
        with pytest.raises(RetryableError):
            operation()
        
        # Verify exponential backoff: 0.1s, 0.2s, 0.4s
        assert len(call_times) == 4
        
        # Check delays (with some tolerance for execution time)
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        delay3 = call_times[3] - call_times[2]
        
        assert 0.08 < delay1 < 0.15  # ~0.1s
        assert 0.18 < delay2 < 0.25  # ~0.2s
        assert 0.38 < delay3 < 0.45  # ~0.4s
    
    def test_retry_operation_functional_approach(self):
        """Test functional retry approach."""
        mock_operation = Mock(
            side_effect=[
                RetryableError("Error 1"),
                'success'
            ]
        )
        
        result = retry_operation(
            operation=mock_operation,
            max_retries=3,
            base_delay=0.1
        )
        
        assert result == 'success'
        assert mock_operation.call_count == 2
    
    def test_retry_with_jitter(self):
        """Test that jitter is applied to delays."""
        call_times = []
        
        def failing_operation():
            call_times.append(time.time())
            raise RetryableError("Error")
        
        @retry_with_backoff(max_retries=2, base_delay=0.1, jitter=True)
        def operation():
            return failing_operation()
        
        with pytest.raises(RetryableError):
            operation()
        
        # With jitter, delays should vary slightly
        # Just verify we have the expected number of attempts
        assert len(call_times) == 3


class TestCircuitBreaker:
    """Test circuit breaker pattern."""
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in CLOSED state allows requests."""
        breaker = CircuitBreaker(name='test', failure_threshold=3, timeout=1.0)
        mock_operation = Mock(return_value='success')
        
        result = breaker.call(mock_operation)
        
        assert result == 'success'
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
    
    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after failure threshold."""
        breaker = CircuitBreaker(name='test', failure_threshold=3, timeout=1.0)
        mock_operation = Mock(side_effect=Exception("Error"))
        
        # Fail 3 times to reach threshold
        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(mock_operation)
        
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3
    
    def test_circuit_breaker_open_fails_fast(self):
        """Test circuit breaker in OPEN state fails fast."""
        breaker = CircuitBreaker(name='test', failure_threshold=2, timeout=1.0)
        mock_operation = Mock(side_effect=Exception("Error"))
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_operation)
        
        assert breaker.state == CircuitState.OPEN
        
        # Next call should fail fast without calling operation
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(mock_operation)
        
        # Operation should not have been called the third time
        assert mock_operation.call_count == 2
    
    def test_circuit_breaker_half_open_transition(self):
        """Test circuit breaker transitions to HALF_OPEN after timeout."""
        breaker = CircuitBreaker(name='test', failure_threshold=2, timeout=0.2)
        mock_operation = Mock(side_effect=Exception("Error"))
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_operation)
        
        assert breaker.state == CircuitState.OPEN
        
        # Wait for timeout
        time.sleep(0.3)
        
        # Next call should transition to HALF_OPEN
        mock_operation.side_effect = None
        mock_operation.return_value = 'success'
        
        result = breaker.call(mock_operation)
        
        assert result == 'success'
        assert breaker.state == CircuitState.CLOSED
    
    def test_circuit_breaker_half_open_to_open_on_failure(self):
        """Test circuit breaker goes back to OPEN if test fails."""
        breaker = CircuitBreaker(name='test', failure_threshold=2, timeout=0.2)
        mock_operation = Mock(side_effect=Exception("Error"))
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_operation)
        
        # Wait for timeout to transition to HALF_OPEN
        time.sleep(0.3)
        
        # Test fails, should go back to OPEN
        with pytest.raises(Exception):
            breaker.call(mock_operation)
        
        assert breaker.state == CircuitState.OPEN
    
    def test_circuit_breaker_decorator(self):
        """Test circuit breaker decorator."""
        @circuit_breaker(name='test', failure_threshold=2, timeout=1.0)
        def risky_operation(should_fail=False):
            if should_fail:
                raise Exception("Error")
            return 'success'
        
        # Should work normally
        result = risky_operation(should_fail=False)
        assert result == 'success'
        
        # Fail twice to open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                risky_operation(should_fail=True)
        
        # Should fail fast now
        with pytest.raises(CircuitBreakerOpenError):
            risky_operation(should_fail=False)
    
    def test_circuit_breaker_reset(self):
        """Test manual circuit breaker reset."""
        breaker = CircuitBreaker(name='test', failure_threshold=2, timeout=1.0)
        mock_operation = Mock(side_effect=Exception("Error"))
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                breaker.call(mock_operation)
        
        assert breaker.state == CircuitState.OPEN
        
        # Reset manually
        breaker.reset()
        
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0


class TestGracefulDegradation:
    """Test graceful degradation utilities."""
    
    def test_with_fallback_returns_fallback_value(self):
        """Test fallback decorator returns fallback value on error."""
        @with_fallback(fallback_value='fallback', log_degradation=False)
        def failing_operation():
            raise Exception("Error")
        
        result = failing_operation()
        
        assert result == 'fallback'
    
    def test_with_fallback_calls_fallback_function(self):
        """Test fallback decorator calls fallback function on error."""
        def fallback_func(exception):
            return f"Handled: {str(exception)}"
        
        @with_fallback(fallback_function=fallback_func, log_degradation=False)
        def failing_operation():
            raise Exception("Test error")
        
        result = failing_operation()
        
        assert result == "Handled: Test error"
    
    def test_with_fallback_success_no_fallback(self):
        """Test fallback decorator doesn't use fallback on success."""
        @with_fallback(fallback_value='fallback', log_degradation=False)
        def successful_operation():
            return 'success'
        
        result = successful_operation()
        
        assert result == 'success'
    
    def test_handle_dynamodb_unavailable(self):
        """Test DynamoDB unavailability handler."""
        response = handle_dynamodb_unavailable('create_session')
        
        assert response['statusCode'] == 503
        assert response['body']['code'] == 'SERVICE_UNAVAILABLE'
        assert response['body']['service'] == 'DynamoDB'
        assert response['body']['retryable'] is True
    
    def test_handle_cognito_unavailable_reject_speakers(self):
        """Test Cognito unavailability rejects speakers."""
        response = handle_cognito_unavailable(
            allow_anonymous=False,
            operation_name='speaker_auth'
        )
        
        assert response['statusCode'] == 503
        assert response['body']['code'] == 'SERVICE_UNAVAILABLE'
        assert response['body']['service'] == 'Cognito'
    
    def test_handle_cognito_unavailable_allow_listeners(self):
        """Test Cognito unavailability allows anonymous listeners."""
        response = handle_cognito_unavailable(
            allow_anonymous=True,
            operation_name='listener_join'
        )
        
        assert response is None
    
    def test_degradation_manager_mark_degraded(self):
        """Test marking service as degraded."""
        manager = GracefulDegradationManager()
        
        manager.mark_degraded('DynamoDB', 'Connection timeout')
        
        assert manager.is_degraded('DynamoDB')
        assert 'DynamoDB' in manager.get_degraded_services()
        assert manager.get_degradation_reason('DynamoDB') == 'Connection timeout'
    
    def test_degradation_manager_mark_recovered(self):
        """Test marking service as recovered."""
        manager = GracefulDegradationManager()
        
        manager.mark_degraded('DynamoDB', 'Connection timeout')
        assert manager.is_degraded('DynamoDB')
        
        manager.mark_recovered('DynamoDB')
        
        assert not manager.is_degraded('DynamoDB')
        assert 'DynamoDB' not in manager.get_degraded_services()
    
    def test_degradation_manager_multiple_services(self):
        """Test tracking multiple degraded services."""
        manager = GracefulDegradationManager()
        
        manager.mark_degraded('DynamoDB', 'Timeout')
        manager.mark_degraded('Cognito', 'Unavailable')
        
        assert manager.is_any_degraded()
        assert len(manager.get_degraded_services()) == 2
        assert 'DynamoDB' in manager.get_degraded_services()
        assert 'Cognito' in manager.get_degraded_services()
    
    def test_get_system_health_healthy(self):
        """Test system health when all services healthy."""
        # Reset global manager
        for service in list(degradation_manager.degraded_services):
            degradation_manager.mark_recovered(service)
        
        health = get_system_health()
        
        assert health['status'] == 'healthy'
        assert len(health['degraded_services']) == 0
    
    def test_get_system_health_degraded(self):
        """Test system health when services degraded."""
        # Reset global manager
        for service in list(degradation_manager.degraded_services):
            degradation_manager.mark_recovered(service)
        
        degradation_manager.mark_degraded('DynamoDB', 'Timeout')
        
        health = get_system_health()
        
        assert health['status'] == 'degraded'
        assert 'DynamoDB' in health['degraded_services']
        assert health['degradation_details']['DynamoDB'] == 'Timeout'
        
        # Cleanup
        degradation_manager.mark_recovered('DynamoDB')


class TestResilienceIntegration:
    """Integration tests for resilience patterns."""
    
    def test_retry_with_circuit_breaker(self):
        """Test retry logic combined with circuit breaker."""
        breaker = CircuitBreaker(name='test', failure_threshold=3, timeout=1.0)
        call_count = {'value': 0}
        
        def operation_with_circuit_breaker():
            call_count['value'] += 1
            
            def inner_operation():
                if call_count['value'] < 3:
                    raise RetryableError("Transient error")
                return 'success'
            
            return breaker.call(inner_operation)
        
        @retry_with_backoff(max_retries=5, base_delay=0.1)
        def resilient_operation():
            return operation_with_circuit_breaker()
        
        result = resilient_operation()
        
        assert result == 'success'
        assert breaker.state == CircuitState.CLOSED
    
    def test_graceful_degradation_with_service_unavailability(self):
        """Test graceful degradation with service unavailability."""
        manager = GracefulDegradationManager()
        
        @with_fallback(fallback_value=False, log_degradation=False)
        def check_rate_limit():
            if manager.is_degraded('RateLimits'):
                # Simulate rate limiting disabled
                return True
            # Simulate rate limit check failure
            raise Exception("RateLimits table unavailable")
        
        # Mark service as degraded
        manager.mark_degraded('RateLimits', 'Table unavailable')
        
        # Should return True (rate limiting disabled)
        result = check_rate_limit()
        assert result is True
        
        # Cleanup
        manager.mark_recovered('RateLimits')
