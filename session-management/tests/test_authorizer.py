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
validate_token = authorizer_handler.validate_token
get_jwks_client = authorizer_handler.get_jwks_client
extract_token = authorizer_handler.extract_token
generate_policy = authorizer_handler.generate_policy


class TestJWTValidation:
    """Test JWT token validation logic."""
    
    def test_valid_token_acceptance(self):
        """Test that valid JWT tokens are accepted."""
        mock_claims = {
            'sub': 'test-user-123',
            'email': 'test@example.com',
            'aud': 'test-client-id',
            'token_use': 'id'
        }
        
        with patch('jwt.decode', return_value=mock_claims):
            with patch.object(authorizer_handler, 'get_jwks_client') as mock_client:
                mock_signing_key = Mock()
                mock_signing_key.key = 'mock-key'
                mock_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key
                
                claims = validate_token('mock-token')
                
                assert claims['sub'] == 'test-user-123'
                assert claims['email'] == 'test@example.com'
                assert claims['aud'] == 'test-client-id'
    
    def test_expired_token_rejection(self):
        """Test that expired tokens are rejected."""
        with patch('jwt.decode', side_effect=jwt.ExpiredSignatureError('Token expired')):
            with patch.object(authorizer_handler, 'get_jwks_client') as mock_client:
                mock_signing_key = Mock()
                mock_signing_key.key = 'mock-key'
                mock_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key
                
                with pytest.raises(jwt.ExpiredSignatureError):
                    validate_token('expired-token')
    
    def test_invalid_signature_rejection(self):
        """Test that tokens with invalid signatures are rejected."""
        with patch('jwt.decode', side_effect=jwt.InvalidSignatureError('Invalid signature')):
            with patch.object(authorizer_handler, 'get_jwks_client') as mock_client:
                mock_signing_key = Mock()
                mock_signing_key.key = 'mock-key'
                mock_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key
                
                with pytest.raises(jwt.InvalidSignatureError):
                    validate_token('invalid-token')
    
    def test_wrong_audience_rejection(self):
        """Test that tokens with wrong audience are rejected."""
        with patch('jwt.decode', side_effect=jwt.InvalidAudienceError('Invalid audience')):
            with patch.object(authorizer_handler, 'get_jwks_client') as mock_client:
                mock_signing_key = Mock()
                mock_signing_key.key = 'mock-key'
                mock_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key
                
                with pytest.raises(jwt.InvalidAudienceError):
                    validate_token('wrong-audience-token')
    
    def test_missing_token_handling(self):
        """Test handling of missing token."""
        event = {
            'queryStringParameters': {},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef/prod/POST/*'
        }
        
        context = Mock()
        context.request_id = 'test-request-123'
        
        with pytest.raises(Exception, match='Unauthorized'):
            lambda_handler(event, context)
    
    def test_malformed_token_handling(self):
        """Test handling of malformed tokens."""
        with patch('jwt.decode', side_effect=jwt.InvalidTokenError('Malformed token')):
            with patch.object(authorizer_handler, 'get_jwks_client') as mock_client:
                mock_signing_key = Mock()
                mock_signing_key.key = 'mock-key'
                mock_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key
                
                with pytest.raises(jwt.InvalidTokenError):
                    validate_token('malformed-token')


class TestIAMPolicyGeneration:
    """Test IAM policy generation."""
    
    def test_allow_policy_structure(self):
        """Test Allow policy has correct structure."""
        policy = generate_policy(
            principal_id='user-123',
            effect='Allow',
            resource='arn:aws:execute-api:*:*:*',
            context={'userId': 'user-123', 'email': 'test@example.com'}
        )
        
        assert policy['principalId'] == 'user-123'
        assert policy['policyDocument']['Version'] == '2012-10-17'
        assert len(policy['policyDocument']['Statement']) == 1
        
        statement = policy['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Allow'
        assert statement['Action'] == 'execute-api:Invoke'
        assert statement['Resource'] == 'arn:aws:execute-api:*:*:*'
        
        assert policy['context']['userId'] == 'user-123'
        assert policy['context']['email'] == 'test@example.com'
    
    def test_deny_policy_structure(self):
        """Test Deny policy has correct structure."""
        policy = generate_policy(
            principal_id='unknown',
            effect='Deny',
            resource='*'
        )
        
        assert policy['principalId'] == 'unknown'
        assert policy['policyDocument']['Statement'][0]['Effect'] == 'Deny'


class TestLambdaHandler:
    """Test Lambda handler integration."""
    
    def test_successful_authorization(self):
        """Test successful authorization flow."""
        event = {
            'queryStringParameters': {
                'token': 'valid-token'
            },
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef/prod/POST/*'
        }
        
        context = Mock()
        context.request_id = 'test-request-123'
        
        mock_claims = {
            'sub': 'test-user-123',
            'email': 'test@example.com',
            'token_use': 'id'
        }
        
        with patch('jwt.decode', return_value=mock_claims):
            with patch.object(authorizer_handler, 'get_jwks_client') as mock_client:
                mock_signing_key = Mock()
                mock_signing_key.key = 'mock-key'
                mock_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key
                
                result = lambda_handler(event, context)
                
                assert result['principalId'] == 'test-user-123'
                assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
                assert result['context']['userId'] == 'test-user-123'
                assert result['context']['email'] == 'test@example.com'
    
    def test_missing_token_raises_exception(self):
        """Test that missing token raises exception."""
        event = {
            'queryStringParameters': {},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef/prod/POST/*'
        }
        
        context = Mock()
        context.request_id = 'test-request-123'
        
        with pytest.raises(Exception, match='Unauthorized'):
            lambda_handler(event, context)
    
    def test_invalid_token_raises_exception(self):
        """Test that invalid token raises exception."""
        event = {
            'queryStringParameters': {
                'token': 'invalid-token'
            },
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef/prod/POST/*'
        }
        
        context = Mock()
        context.request_id = 'test-request-123'
        
        with patch('jwt.decode', side_effect=jwt.InvalidTokenError('Invalid token')):
            with patch.object(authorizer_handler, 'get_jwks_client') as mock_client:
                mock_signing_key = Mock()
                mock_signing_key.key = 'mock-key'
                mock_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key
                
                with pytest.raises(Exception, match='Unauthorized'):
                    lambda_handler(event, context)
    
    def test_expired_token_raises_exception(self):
        """Test that expired token raises exception."""
        event = {
            'queryStringParameters': {
                'token': 'expired-token'
            },
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef/prod/POST/*'
        }
        
        context = Mock()
        context.request_id = 'test-request-123'
        
        with patch('jwt.decode', side_effect=jwt.ExpiredSignatureError('Token expired')):
            with patch.object(authorizer_handler, 'get_jwks_client') as mock_client:
                mock_signing_key = Mock()
                mock_signing_key.key = 'mock-key'
                mock_client.return_value.get_signing_key_from_jwt.return_value = mock_signing_key
                
                with pytest.raises(Exception, match='Unauthorized'):
                    lambda_handler(event, context)


class TestExtractToken:
    """Test token extraction from event."""
    
    def test_extract_from_query_string(self):
        """Test extracting token from query string."""
        event = {
            'queryStringParameters': {
                'token': 'test-token-123'
            }
        }
        
        token = extract_token(event)
        assert token == 'test-token-123'
    
    def test_extract_from_authorization_header(self):
        """Test extracting token from Authorization header."""
        event = {
            'queryStringParameters': {},
            'headers': {
                'Authorization': 'Bearer test-token-456'
            }
        }
        
        token = extract_token(event)
        assert token == 'test-token-456'
    
    def test_query_string_takes_precedence(self):
        """Test that query string takes precedence over header."""
        event = {
            'queryStringParameters': {
                'token': 'query-token'
            },
            'headers': {
                'Authorization': 'Bearer header-token'
            }
        }
        
        token = extract_token(event)
        assert token == 'query-token'
    
    def test_no_token_returns_none(self):
        """Test that missing token returns None."""
        event = {
            'queryStringParameters': {},
            'headers': {}
        }
        
        token = extract_token(event)
        assert token is None
