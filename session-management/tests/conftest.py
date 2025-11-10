"""
Pytest configuration and fixtures.
"""
import pytest
import os


@pytest.fixture(scope="session")
def aws_credentials():
    """Mock AWS credentials for testing."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def env_vars():
    """Set up environment variables for tests."""
    os.environ["ENV"] = "test"
    os.environ["SESSIONS_TABLE"] = "Sessions-test"
    os.environ["CONNECTIONS_TABLE"] = "Connections-test"
    os.environ["RATE_LIMITS_TABLE"] = "RateLimits-test"
    os.environ["SESSION_MAX_DURATION_HOURS"] = "2"
    os.environ["MAX_LISTENERS_PER_SESSION"] = "500"
    os.environ["CONNECTION_REFRESH_MINUTES"] = "100"
    os.environ["CONNECTION_WARNING_MINUTES"] = "105"
