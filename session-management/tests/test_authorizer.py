"""
Unit tests for Lambda Authorizer.

Tests JWT validation logic, IAM policy generation, and error handling.

Requirements: 7, 19
"""

import json
import os
import time
from unittest.mock import Mock, patch, MagicMock
import pytest
import jwt
from jwt.algorithms import RSAAlgorithm
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


# Set environment variables for testing
os.environ['REGION'] = 'us-east-1'
os.environ['USER_POOL_ID'] = 'us-east-1_TEST123'
os.environ['CLIENT_ID'] = 'test-client-id'

# Import after setting environment variables
import sys
import importlib.util
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import using importlib to avoid 'lambda' keyword issue
handler_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'authorizer', 'handler.py')
spec = importlib.util.spec_from_file_location('authorizer_handler', handler_path)
authorizer_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(authorizer_handler)

lambda_handler = authorizer_handler.lambda_handler
validate_jwt_token = authorizer_handler.validate_jwt_token
get_cognito_public_keys = authorizer_handler.get_cognito_public_keys
verify_jwt_signature = authorizer_handler.verify_jwt_signature
deny_policy = authorizer_handler.deny_policy


class TestJWTValidation:
    """Test JWT token validation logic."""
    
    @pytest.fixture
    def rsa_key_pair(self):
        """Generate RSA key pair for testing."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        return private_key, public_key
    
    @pytest.fixture
    def mock_jwks(self, rsa_key_pair):
        """Create mock JWKS response (already processed format)."""
        _, public_key = rsa_key_pair
        
        # Convert public key to JWK format
        public_numbers = public_key.public_numbers()
        
        # Return in the format that get_cognito_public_keys returns (kid -> key data)
        return {
            'test-key-id': {
                'kid': 'test-key-id',
                'kty': 'RSA',
                'use': 'sig',
                'alg': 'RS256',
                'n': jwt.utils.base64url_encode(
                    public_numbers.n.to_bytes(256, byteorder='big')
                ).decode('utf-8'),
                'e': jwt.utils.base64url_encode(
                    public_numbers.e.to_bytes(3, byteorder='big')
                ).decode('utf-8')
            }
        }
    
    @pytest.fixture
    def valid_token(self, rsa_key_pair):
        """Generate valid JWT token."""
        private_key, _ = rsa_key_pair
        
        # Create token claims
        claims = {
            'sub': 'test-user-123',
            'email': 'test@example.com',
            'aud': 'test-client-id',
            'iss': 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST123',
            'token_use': 'id',
            'exp': int(time.time()) + 3600,  # Expires in 1 hour
            'iat': int(time.time())
        }
        
        # Sign token
        token = jwt.encode(
            claims,
            private_key,
            algorithm='RS256',
            headers={'kid': 'test-key-id'}
        )
        
        return token
    
    @pytest.fixture
    def expired_token(self, rsa_key_pair):
        """Generate expired JWT token."""
        private_key, _ = rsa_key_pair
        
        claims = {
            'sub': 'test-user-123',
            'email': 'test@example.com',
            'aud': 'test-client-id',
            'iss': 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST123',
            'token_use': 'id',
            'exp': int(time.time()) - 3600,  # Expired 1 hour ago
            'iat': int(time.time()) - 7200
        }
        
        token = jwt.encode(
            claims,
            private_key,
            algorithm='RS256',
            headers={'kid': 'test-key-id'}
        )
        
        return token
    
    @pytest.fixture
    def wrong_audience_token(self, rsa_key_pair):
        """Generate token with wrong audience."""
        private_key, _ = rsa_key_pair
        
        claims = {
            'sub': 'test-user-123',
            'email': 'test@example.com',
            'aud': 'wrong-client-id',  # Wrong audience
            'iss': 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST123',
            'token_use': 'id',
            'exp': int(time.time()) + 3600,
            'iat': int(time.time())
        }
        
        token = jwt.encode(
            claims,
            private_key,
            algorithm='RS256',
            headers={'kid': 'test-key-id'}
        )
        
        return token
    
    def test_valid_token_acceptance(self, valid_token, mock_jwks):
        """Test that valid JWT tokens are accepted."""
        with patch.object(authorizer_handler, 'get_cognito_public_keys', return_value=mock_jwks):
            claims = validate_jwt_token(valid_token)
            
            assert claims['sub'] == 'test-user-123'
            assert claims['email'] == 'test@example.com'
            assert claims['aud'] == 'test-client-id'
    
    def test_expired_token_rejection(self, expired_token, mock_jwks):
        """Test that expired tokens are rejected."""
        with patch.object(authorizer_handler, 'get_cognito_public_keys', return_value=mock_jwks):
            claims = validate_jwt_token(expired_token)
            assert claims is None  # Expired tokens return None
    
    def test_invalid_signature_rejection(self, rsa_key_pair, mock_jwks):
        """Test that tokens with invalid signatures are rejected."""
        # Generate token with different key
        different_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        claims = {
            'sub': 'test-user-123',
            'aud': 'test-client-id',
            'iss': 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST123',
            'exp': int(time.time()) + 3600,
            'iat': int(time.time())
        }
        
        invalid_token = jwt.encode(
            claims,
            different_key,
            algorithm='RS256',
            headers={'kid': 'test-key-id'}
        )
        
        with patch.object(authorizer_handler, 'get_cognito_public_keys', return_value=mock_jwks):
            claims_result = validate_jwt_token(invalid_token)
            assert claims_result is None  # Invalid signature returns None
    
    def test_wrong_audience_rejection(self, wrong_audience_token, mock_jwks):
        """Test that tokens with wrong audience are rejected."""
        with patch.object(authorizer_handler, 'get_cognito_public_keys', return_value=mock_jwks):
            claims = validate_jwt_token(wrong_audience_token)
            assert claims is None  # Wrong audience returns None
    
    def test_missing_token_handling(self):
        """Test handling of missing token."""
        event = {
            'queryStringParameters': {},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef/prod/POST/*'
        }
        
        context = Mock()
        context.request_id = 'test-request-123'
        
        result = lambda_handler(event, context)
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    
    def test_malformed_token_handling(self, mock_jwks):
        """Test handling of malformed tokens."""
        with patch.object(authorizer_handler, 'get_cognito_public_keys', return_value=mock_jwks):
            claims = validate_jwt_token('not-a-valid-jwt-token')
            assert claims is None  # Malformed tokens return None


class TestIAMPolicyGeneration:
    """Test IAM policy generation."""
    
    def test_deny_policy_structure(self):
        """Test Deny policy has correct structure."""
        policy = deny_policy("Test reason")
        
        assert policy['principalId'] == 'unknown'
        assert policy['policyDocument']['Version'] == '2012-10-17'
        assert len(policy['policyDocument']['Statement']) == 1
        
        statement = policy['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Deny'
        assert statement['Action'] == 'execute-api:Invoke'
        assert statement['Resource'] == '*'
        
        assert policy['context']['reason'] == 'Test reason'
    
    def test_deny_policy_default_reason(self):
        """Test Deny policy with default reason."""
        policy = deny_policy()
        
        assert policy['principalId'] == 'unknown'
        assert policy['context']['reason'] == 'Unauthorized'


class TestLambdaHandler:
    """Test Lambda handler integration."""
    
    @pytest.fixture
    def rsa_key_pair(self):
        """Generate RSA key pair for testing."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        return private_key, public_key
    
    @pytest.fixture
    def valid_event(self, rsa_key_pair):
        """Create valid authorization event."""
        private_key, _ = rsa_key_pair
        
        claims = {
            'sub': 'test-user-123',
            'email': 'test@example.com',
            'aud': 'test-client-id',
            'iss': 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST123',
            'token_use': 'id',
            'exp': int(time.time()) + 3600,
            'iat': int(time.time())
        }
        
        token = jwt.encode(
            claims,
            private_key,
            algorithm='RS256',
            headers={'kid': 'test-key-id'}
        )
        
        return {
            'queryStringParameters': {
                'token': token
            },
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef/prod/POST/*'
        }
    
    @pytest.fixture
    def mock_jwks(self, rsa_key_pair):
        """Create mock JWKS response (already processed format)."""
        _, public_key = rsa_key_pair
        public_numbers = public_key.public_numbers()
        
        # Return in the format that get_cognito_public_keys returns (kid -> key data)
        return {
            'test-key-id': {
                'kid': 'test-key-id',
                'kty': 'RSA',
                'use': 'sig',
                'alg': 'RS256',
                'n': jwt.utils.base64url_encode(
                    public_numbers.n.to_bytes(256, byteorder='big')
                ).decode('utf-8'),
                'e': jwt.utils.base64url_encode(
                    public_numbers.e.to_bytes(3, byteorder='big')
                ).decode('utf-8')
            }
        }
    
    def test_successful_authorization(self, valid_event, mock_jwks):
        """Test successful authorization flow."""
        context = Mock()
        context.request_id = 'test-request-123'
        
        with patch.object(authorizer_handler, 'get_cognito_public_keys', return_value=mock_jwks):
            result = lambda_handler(valid_event, context)
            
            assert result['principalId'] == 'test-user-123'
            assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
            assert result['context']['userId'] == 'test-user-123'
            assert result['context']['email'] == 'test@example.com'
    
    def test_missing_token_returns_deny(self):
        """Test that missing token returns Deny policy."""
        event = {
            'queryStringParameters': {},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef/prod/POST/*'
        }
        
        context = Mock()
        context.request_id = 'test-request-123'
        
        result = lambda_handler(event, context)
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    
    def test_invalid_token_returns_deny(self, mock_jwks):
        """Test that invalid token returns Deny policy."""
        event = {
            'queryStringParameters': {
                'token': 'invalid-token'
            },
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef/prod/POST/*'
        }
        
        context = Mock()
        context.request_id = 'test-request-123'
        
        with patch.object(authorizer_handler, 'get_cognito_public_keys', return_value=mock_jwks):
            result = lambda_handler(event, context)
            
            assert result['principalId'] == 'unknown'
            assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    
    def test_error_logging_on_failure(self, mock_jwks):
        """Test that authorization failures return Deny policy."""
        event = {
            'queryStringParameters': {
                'token': 'invalid-token'
            },
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef/prod/POST/*'
        }
        
        context = Mock()
        context.request_id = 'test-request-123'
        
        with patch.object(authorizer_handler, 'get_cognito_public_keys', return_value=mock_jwks):
            result = lambda_handler(event, context)
            
            # Verify Deny policy returned
            assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
            assert result['principalId'] == 'unknown'


class TestCognitoPublicKeys:
    """Test Cognito public key fetching and caching."""
    
    def test_public_keys_cached(self):
        """Test that public keys are cached."""
        # Clear cache before test
        authorizer_handler._cognito_keys_cache = {}
        authorizer_handler._cache_timestamp = 0
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({'keys': [{'kid': 'test-key'}]}).encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        
        with patch.object(authorizer_handler, 'urlopen', return_value=mock_response) as mock_urlopen:
            with patch.dict(os.environ, {'USER_POOL_ID': 'test-pool'}):
                # First call
                keys1 = get_cognito_public_keys()
                # Second call should use cache
                keys2 = get_cognito_public_keys()
                
                # Should only call urlopen once due to caching
                assert mock_urlopen.call_count == 1
                assert keys1 == keys2
    
    def test_public_key_fetch_failure(self):
        """Test handling of public key fetch failures."""
        # Mock urlopen to raise exception
        with patch('urllib.request.urlopen', side_effect=Exception('Network error')):
            with patch.dict(os.environ, {'USER_POOL_ID': 'test-pool'}):
                keys = get_cognito_public_keys()
                # Should return empty dict on failure
                assert keys == {}
