"""
Security tests for Lambda Authorizer.
Tests JWT validation, expiration, audience, issuer, and signature verification.
"""
import json
import os
import time
import base64
import sys
import pytest
from unittest.mock import Mock, patch
import importlib.util

# Import authorizer handler using importlib to avoid 'lambda' keyword issue
handler_path = os.path.join(os.path.dirname(__file__), '..', 'lambda', 'authorizer', 'handler.py')
spec = importlib.util.spec_from_file_location('authorizer_handler', handler_path)
authorizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(authorizer)


class TestJWTSecurityValidation:
    """Test JWT security validation scenarios."""

    def test_missing_token_rejected(self):
        """Test that missing token is rejected."""
        event = {
            'queryStringParameters': {},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
        assert result['context']['reason'] == 'No token provided'

    def test_invalid_token_format_rejected(self):
        """Test that invalid token format is rejected."""
        event = {
            'queryStringParameters': {'token': 'invalid-token-format'},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'
        assert result['context']['reason'] == 'Invalid JWT format'

    def test_token_with_only_two_parts_rejected(self):
        """Test that token with only 2 parts is rejected."""
        event = {
            'queryStringParameters': {'token': 'header.payload'},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    def test_token_with_four_parts_rejected(self):
        """Test that token with 4 parts is rejected."""
        event = {
            'queryStringParameters': {'token': 'header.payload.signature.extra'},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    def test_missing_key_id_rejected(self):
        """Test that JWT with missing key ID is rejected."""
        # Create JWT with header missing 'kid'
        header = json.dumps({'alg': 'RS256'})
        payload = json.dumps({'sub': 'user-123', 'exp': int(time.time()) + 3600})
        
        header_b64 = base64.urlsafe_b64encode(header.encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
        signature_b64 = 'fake-signature'
        
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        event = {
            'queryStringParameters': {'token': token},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    def test_unknown_key_id_rejected(self):
        """Test that JWT with unknown key ID is rejected."""
        # Create JWT with unknown key ID
        header = json.dumps({'alg': 'RS256', 'kid': 'unknown-key-id'})
        payload = json.dumps({'sub': 'user-123', 'exp': int(time.time()) + 3600})
        
        header_b64 = base64.urlsafe_b64encode(header.encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
        signature_b64 = 'fake-signature'
        
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        event = {
            'queryStringParameters': {'token': token},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        # Mock public keys without the key ID used in token
        with patch.object(authorizer, 'get_cognito_public_keys', return_value={'known-key-id': {'n': 'abc', 'e': 'def'}}):
            result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    def test_expired_token_rejected(self):
        """Test that expired token is rejected."""
        # Create expired JWT
        header = json.dumps({'alg': 'RS256', 'kid': 'test-key-id'})
        payload = json.dumps({
            'sub': 'user-123',
            'aud': 'test-client-id',
            'iss': 'https://cognito-idp.us-east-1.amazonaws.com/test-pool',
            'token_use': 'id',
            'exp': int(time.time()) - 3600  # Expired 1 hour ago
        })
        
        header_b64 = base64.urlsafe_b64encode(header.encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
        signature_b64 = 'fake-signature'
        
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        event = {
            'queryStringParameters': {'token': token},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        # Mock keys and signature verification
        with patch.object(authorizer, 'get_cognito_public_keys', return_value={'test-key-id': {'n': 'abc', 'e': 'def'}}):
            with patch.object(authorizer, 'verify_jwt_signature', return_value=True):
                with patch.dict(os.environ, {'USER_POOL_ID': 'test-pool', 'CLIENT_ID': 'test-client-id'}):
                    result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    def test_wrong_audience_rejected(self):
        """Test that token with wrong audience is rejected."""
        # Create JWT with wrong audience
        header = json.dumps({'alg': 'RS256', 'kid': 'test-key-id'})
        payload = json.dumps({
            'sub': 'user-123',
            'aud': 'wrong-client-id',  # Wrong audience
            'iss': 'https://cognito-idp.us-east-1.amazonaws.com/test-pool',
            'token_use': 'id',
            'exp': int(time.time()) + 3600
        })
        
        header_b64 = base64.urlsafe_b64encode(header.encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
        signature_b64 = 'fake-signature'
        
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        event = {
            'queryStringParameters': {'token': token},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        # Mock keys and signature verification
        with patch.object(authorizer, 'get_cognito_public_keys', return_value={'test-key-id': {'n': 'abc', 'e': 'def'}}):
            with patch.object(authorizer, 'verify_jwt_signature', return_value=True):
                with patch.dict(os.environ, {'USER_POOL_ID': 'test-pool', 'CLIENT_ID': 'correct-client-id'}):
                    result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    def test_wrong_issuer_rejected(self):
        """Test that token with wrong issuer is rejected."""
        # Create JWT with wrong issuer
        header = json.dumps({'alg': 'RS256', 'kid': 'test-key-id'})
        payload = json.dumps({
            'sub': 'user-123',
            'aud': 'test-client-id',
            'iss': 'https://evil-issuer.com/fake-pool',  # Wrong issuer
            'token_use': 'id',
            'exp': int(time.time()) + 3600
        })
        
        header_b64 = base64.urlsafe_b64encode(header.encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
        signature_b64 = 'fake-signature'
        
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        event = {
            'queryStringParameters': {'token': token},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        # Mock keys and signature verification
        with patch.object(authorizer, 'get_cognito_public_keys', return_value={'test-key-id': {'n': 'abc', 'e': 'def'}}):
            with patch.object(authorizer, 'verify_jwt_signature', return_value=True):
                with patch.dict(os.environ, {'USER_POOL_ID': 'test-pool', 'CLIENT_ID': 'test-client-id'}):
                    result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    def test_invalid_signature_rejected(self):
        """Test that token with invalid signature is rejected."""
        # Create JWT with valid claims but invalid signature
        header = json.dumps({'alg': 'RS256', 'kid': 'test-key-id'})
        payload = json.dumps({
            'sub': 'user-123',
            'aud': 'test-client-id',
            'iss': 'https://cognito-idp.us-east-1.amazonaws.com/test-pool',
            'token_use': 'id',
            'exp': int(time.time()) + 3600
        })
        
        header_b64 = base64.urlsafe_b64encode(header.encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
        signature_b64 = 'invalid-signature'  # This will fail verification
        
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        event = {
            'queryStringParameters': {'token': token},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        # Mock public keys
        with patch.object(authorizer, 'get_cognito_public_keys', return_value={'test-key-id': {'n': 'abc', 'e': 'def'}}):
            with patch.dict(os.environ, {'USER_POOL_ID': 'test-pool', 'CLIENT_ID': 'test-client-id'}):
                result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    def test_valid_token_accepted(self):
        """Test that valid token is accepted."""
        # Create valid JWT
        header = json.dumps({'alg': 'RS256', 'kid': 'test-key-id'})
        payload = json.dumps({
            'sub': 'user-123',
            'aud': 'test-client-id',
            'iss': 'https://cognito-idp.us-east-1.amazonaws.com/test-pool',
            'token_use': 'id',
            'exp': int(time.time()) + 3600,
            'email': 'user@example.com'
        })
        
        header_b64 = base64.urlsafe_b64encode(header.encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
        signature_b64 = 'valid-signature'
        
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        event = {
            'queryStringParameters': {'token': token},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        # Mock keys and signature verification
        with patch.object(authorizer, 'get_cognito_public_keys', return_value={'test-key-id': {'n': 'abc', 'e': 'def'}}):
            with patch.object(authorizer, 'verify_jwt_signature', return_value=True):
                with patch.dict(os.environ, {'USER_POOL_ID': 'test-pool', 'CLIENT_ID': 'test-client-id'}):
                    result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'user-123'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert result['context']['userId'] == 'user-123'
        assert result['context']['email'] == 'user@example.com'

    def test_missing_sub_claim_rejected(self):
        """Test that token missing sub claim is rejected."""
        # Create JWT with missing sub claim
        header = json.dumps({'alg': 'RS256', 'kid': 'test-key-id'})
        payload = json.dumps({
            # 'sub': missing
            'aud': 'test-client-id',
            'iss': 'https://cognito-idp.us-east-1.amazonaws.com/test-pool',
            'token_use': 'id',
            'exp': int(time.time()) + 3600
        })
        
        header_b64 = base64.urlsafe_b64encode(header.encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
        signature_b64 = 'fake-signature'
        
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        event = {
            'queryStringParameters': {'token': token},
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:abcdef123/*'
        }
        
        with patch.object(authorizer, 'get_cognito_public_keys', return_value={'test-key-id': {'n': 'abc', 'e': 'def'}}):
            with patch.dict(os.environ, {'USER_POOL_ID': 'test-pool'}):
                result = authorizer.lambda_handler(event, {})
        
        assert result['principalId'] == 'unknown'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'


class TestCognitoPublicKeyFetching:
    """Test Cognito public key fetching and caching."""

    def test_public_keys_fetched_successfully(self):
        """Test that public keys are fetched from Cognito."""
        # Clear cache before test
        authorizer._cognito_keys_cache = {}
        authorizer._cache_timestamp = 0
        
        # Mock HTTP response
        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'keys': [
                {'kid': 'key1', 'n': 'modulus1', 'e': 'exponent1'},
                {'kid': 'key2', 'n': 'modulus2', 'e': 'exponent2'}
            ]
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        
        with patch.object(authorizer, 'urlopen', return_value=mock_response):
            with patch.object(authorizer, 'time') as mock_time:
                mock_time.time.return_value = 1000000  # Fixed timestamp
                with patch.dict(os.environ, {'USER_POOL_ID': 'test-pool', 'REGION': 'us-east-1'}):
                    keys = authorizer.get_cognito_public_keys()
        
        assert len(keys) == 2
        assert 'key1' in keys
        assert 'key2' in keys
        assert keys['key1']['n'] == 'modulus1'

    def test_public_keys_caching(self):
        """Test that public keys are cached for performance."""
        # Clear cache before test
        authorizer._cognito_keys_cache = {}
        authorizer._cache_timestamp = 0
        
        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({'keys': []}).encode()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        
        with patch.object(authorizer, 'urlopen', return_value=mock_response) as mock_urlopen:
            with patch.object(authorizer, 'time') as mock_time:
                mock_time.time.return_value = 1000000  # Fixed timestamp for both calls
                with patch.dict(os.environ, {'USER_POOL_ID': 'test-pool'}):
                    # First call
                    keys1 = authorizer.get_cognito_public_keys()
                    
                    # Second call (should use cache)
                    keys2 = authorizer.get_cognito_public_keys()
            
            # Should only call urlopen once due to caching
            assert mock_urlopen.call_count == 1
            assert keys1 == keys2

    def test_missing_user_pool_id_returns_empty(self):
        """Test that missing USER_POOL_ID returns empty keys."""
        with patch.dict(os.environ, {}, clear=True):  # Clear all env vars
            keys = authorizer.get_cognito_public_keys()
        
        assert keys == {}


class TestRSASignatureVerification:
    """Test RSA signature verification functionality."""

    def test_signature_verification_requires_cryptography(self):
        """Test that signature verification fails gracefully without cryptography."""
        with patch.dict('sys.modules', {'cryptography': None}):
            result = authorizer.verify_jwt_signature(
                'header', 'payload', 'signature',
                {'n': 'modulus', 'e': 'exponent'}
            )
        
        # Should fail securely if cryptography not available
        assert result is False

    def test_invalid_signature_data_rejected(self):
        """Test that malformed signature data is rejected."""
        # Test with invalid base64 in signature
        result = authorizer.verify_jwt_signature(
            'header', 'payload', 'invalid@base64!',
            {'n': 'validmodulus', 'e': 'validexponent'}
        )
        
        assert result is False

    def test_malformed_public_key_rejected(self):
        """Test that malformed public key data is rejected."""
        result = authorizer.verify_jwt_signature(
            'header', 'payload', 'signature',
            {'n': 'invalid-base64!', 'e': 'invalid-base64!'}
        )
        
        assert result is False


class TestDenyPolicyGeneration:
    """Test deny policy generation."""

    def test_deny_policy_structure(self):
        """Test that deny policy has correct structure."""
        policy = authorizer.deny_policy("Test reason")
        
        assert policy['principalId'] == 'unknown'
        assert policy['policyDocument']['Version'] == '2012-10-17'
        assert len(policy['policyDocument']['Statement']) == 1
        
        statement = policy['policyDocument']['Statement'][0]
        assert statement['Action'] == 'execute-api:Invoke'
        assert statement['Effect'] == 'Deny'
        assert statement['Resource'] == '*'
        
        assert policy['context']['reason'] == 'Test reason'

    def test_default_deny_reason(self):
        """Test default reason in deny policy."""
        policy = authorizer.deny_policy()
        
        assert policy['context']['reason'] == 'Unauthorized'


class TestBase64URLDecoding:
    """Test base64 URL decoding utility."""

    def test_decode_with_padding(self):
        """Test decoding base64 URL with proper padding."""
        # Test data that needs padding
        data = "eyJhbGciOiJSUzI1NiJ"  # Missing padding (19 chars, needs 1 '=' to make 20)
        result = authorizer.decode_base64_url(data)
        
        # The function adds padding, so result should match the padded version
        expected = base64.urlsafe_b64decode("eyJhbGciOiJSUzI1NiJ=")  # With padding
        assert result == expected

    def test_decode_without_padding_needed(self):
        """Test decoding base64 URL that doesn't need padding."""
        data = "eyJhbGciOiJSUzI1NiJ9"  # Already has padding
        result = authorizer.decode_base64_url(data)
        
        expected = base64.urlsafe_b64decode(data)
        assert result == expected

    def test_decode_invalid_base64_raises_exception(self):
        """Test that invalid base64 raises exception."""
        with pytest.raises(Exception):
            authorizer.decode_base64_url("invalid@base64!")
