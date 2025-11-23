"""
Unit tests for Lambda authorizer
"""
import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import jwt
from jwt import PyJWKClient

# Import the handler module
import sys
import importlib.util

# Use importlib to avoid 'lambda' keyword issue
handler_path = os.path.join(os.path.dirname(__file__), '../../lambda/authorizer/handler.py')
spec = importlib.util.spec_from_file_location('handler', handler_path)
handler = importlib.util.module_from_spec(spec)
sys.modules['handler'] = handler
spec.loader.exec_module(handler)

lambda_handler = handler.lambda_handler
extract_token = handler.extract_token
validate_token = handler.validate_token
generate_policy = handler.generate_policy
get_jwks_client = handler.get_jwks_client


@pytest.fixture
def mock_env():
    """Mock environment variables"""
    with patch.dict(os.environ, {
        'USER_POOL_ID': 'us-east-1_TEST123',
        'CLIENT_ID': 'test-client-id',
        'REGION': 'us-east-1',
    }):
        yield


@pytest.fixture
def valid_token_claims():
    """Valid token claims"""
    return {
        'sub': 'user-123',
        'email': 'test@example.com',
        'token_use': 'id',
        'iss': 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST123',
        'aud': 'test-client-id',
        'exp': 9999999999,  # Far future
        'iat': 1234567890,
    }


@pytest.fixture
def api_gateway_event():
    """API Gateway authorizer event"""
    return {
        'type': 'REQUEST',
        'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abcdef123/prod/POST/@connections',
        'queryStringParameters': {},
        'headers': {},
    }


class TestExtractToken:
    """Tests for extract_token function"""

    def test_extract_token_from_query_string(self, api_gateway_event):
        """Test extracting token from query string"""
        api_gateway_event['queryStringParameters'] = {'token': 'test-token-123'}
        
        token = extract_token(api_gateway_event)
        
        assert token == 'test-token-123'

    def test_extract_token_from_authorization_header(self, api_gateway_event):
        """Test extracting token from Authorization header"""
        api_gateway_event['headers'] = {'Authorization': 'Bearer test-token-456'}
        
        token = extract_token(api_gateway_event)
        
        assert token == 'test-token-456'

    def test_extract_token_from_lowercase_authorization_header(self, api_gateway_event):
        """Test extracting token from lowercase authorization header"""
        api_gateway_event['headers'] = {'authorization': 'Bearer test-token-789'}
        
        token = extract_token(api_gateway_event)
        
        assert token == 'test-token-789'

    def test_extract_token_priority_query_over_header(self, api_gateway_event):
        """Test that query string takes priority over header"""
        api_gateway_event['queryStringParameters'] = {'token': 'query-token'}
        api_gateway_event['headers'] = {'Authorization': 'Bearer header-token'}
        
        token = extract_token(api_gateway_event)
        
        assert token == 'query-token'

    def test_extract_token_no_token(self, api_gateway_event):
        """Test extracting token when none provided"""
        token = extract_token(api_gateway_event)
        
        assert token is None

    def test_extract_token_invalid_bearer_format(self, api_gateway_event):
        """Test extracting token with invalid Bearer format"""
        api_gateway_event['headers'] = {'Authorization': 'InvalidFormat token'}
        
        token = extract_token(api_gateway_event)
        
        assert token is None


class TestValidateToken:
    """Tests for validate_token function"""

    @patch('handler.get_jwks_client')
    @patch('handler.jwt.decode')
    def test_validate_token_success(self, mock_decode, mock_get_jwks_client, mock_env, valid_token_claims):
        """Test successful token validation"""
        # Mock JWKS client
        mock_client = Mock()
        mock_signing_key = Mock()
        mock_signing_key.key = 'mock-key'
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_jwks_client.return_value = mock_client
        
        # Mock jwt.decode
        mock_decode.return_value = valid_token_claims
        
        result = validate_token('test-token')
        
        assert result == valid_token_claims
        mock_decode.assert_called_once()

    @patch('handler.get_jwks_client')
    @patch('handler.jwt.decode')
    def test_validate_token_expired(self, mock_decode, mock_get_jwks_client, mock_env):
        """Test token validation with expired token"""
        mock_client = Mock()
        mock_signing_key = Mock()
        mock_signing_key.key = 'mock-key'
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_jwks_client.return_value = mock_client
        
        mock_decode.side_effect = jwt.ExpiredSignatureError('Token expired')
        
        with pytest.raises(jwt.ExpiredSignatureError):
            validate_token('expired-token')

    @patch('handler.get_jwks_client')
    @patch('handler.jwt.decode')
    def test_validate_token_invalid_signature(self, mock_decode, mock_get_jwks_client, mock_env):
        """Test token validation with invalid signature"""
        mock_client = Mock()
        mock_signing_key = Mock()
        mock_signing_key.key = 'mock-key'
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_jwks_client.return_value = mock_client
        
        mock_decode.side_effect = jwt.InvalidSignatureError('Invalid signature')
        
        with pytest.raises(jwt.InvalidSignatureError):
            validate_token('invalid-token')

    @patch('handler.get_jwks_client')
    @patch('handler.jwt.decode')
    def test_validate_token_invalid_issuer(self, mock_decode, mock_get_jwks_client, mock_env):
        """Test token validation with invalid issuer"""
        mock_client = Mock()
        mock_signing_key = Mock()
        mock_signing_key.key = 'mock-key'
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_jwks_client.return_value = mock_client
        
        mock_decode.side_effect = jwt.InvalidIssuerError('Invalid issuer')
        
        with pytest.raises(jwt.InvalidIssuerError):
            validate_token('invalid-issuer-token')

    @patch('handler.get_jwks_client')
    @patch('handler.jwt.decode')
    def test_validate_token_invalid_audience(self, mock_decode, mock_get_jwks_client, mock_env):
        """Test token validation with invalid audience"""
        mock_client = Mock()
        mock_signing_key = Mock()
        mock_signing_key.key = 'mock-key'
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_jwks_client.return_value = mock_client
        
        mock_decode.side_effect = jwt.InvalidAudienceError('Invalid audience')
        
        with pytest.raises(jwt.InvalidAudienceError):
            validate_token('invalid-audience-token')

    @patch('handler.get_jwks_client')
    @patch('handler.jwt.decode')
    def test_validate_token_wrong_token_use(self, mock_decode, mock_get_jwks_client, mock_env, valid_token_claims):
        """Test token validation with wrong token_use"""
        mock_client = Mock()
        mock_signing_key = Mock()
        mock_signing_key.key = 'mock-key'
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_jwks_client.return_value = mock_client
        
        # Return claims with wrong token_use
        claims = valid_token_claims.copy()
        claims['token_use'] = 'access'
        mock_decode.return_value = claims
        
        with pytest.raises(jwt.InvalidTokenError):
            validate_token('access-token')


class TestGeneratePolicy:
    """Tests for generate_policy function"""

    def test_generate_allow_policy(self):
        """Test generating allow policy"""
        policy = generate_policy(
            principal_id='user-123',
            effect='Allow',
            resource='arn:aws:execute-api:us-east-1:123456789012:abcdef123/prod/POST/@connections'
        )
        
        assert policy['principalId'] == 'user-123'
        assert policy['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert policy['policyDocument']['Statement'][0]['Action'] == 'execute-api:Invoke'

    def test_generate_deny_policy(self):
        """Test generating deny policy"""
        policy = generate_policy(
            principal_id='unknown',
            effect='Deny',
            resource='*'
        )
        
        assert policy['principalId'] == 'unknown'
        assert policy['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    def test_generate_policy_with_context(self):
        """Test generating policy with context"""
        context = {
            'userId': 'user-123',
            'email': 'test@example.com',
        }
        
        policy = generate_policy(
            principal_id='user-123',
            effect='Allow',
            resource='arn:aws:execute-api:us-east-1:123456789012:abcdef123/prod/POST/@connections',
            context=context
        )
        
        assert policy['context'] == context


class TestLambdaHandler:
    """Tests for lambda_handler function"""

    @patch('handler.validate_token')
    @patch('handler.extract_token')
    def test_lambda_handler_success(self, mock_extract_token, mock_validate_token, mock_env, api_gateway_event, valid_token_claims):
        """Test successful authorization"""
        mock_extract_token.return_value = 'valid-token'
        mock_validate_token.return_value = valid_token_claims
        
        result = lambda_handler(api_gateway_event, None)
        
        assert result['principalId'] == 'user-123'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert result['context']['userId'] == 'user-123'
        assert result['context']['email'] == 'test@example.com'

    @patch('handler.extract_token')
    def test_lambda_handler_no_token(self, mock_extract_token, mock_env, api_gateway_event):
        """Test authorization with no token"""
        mock_extract_token.return_value = None
        
        with pytest.raises(Exception) as exc_info:
            lambda_handler(api_gateway_event, None)
        
        assert str(exc_info.value) == 'Unauthorized'

    @patch('handler.validate_token')
    @patch('handler.extract_token')
    def test_lambda_handler_expired_token(self, mock_extract_token, mock_validate_token, mock_env, api_gateway_event):
        """Test authorization with expired token"""
        mock_extract_token.return_value = 'expired-token'
        mock_validate_token.side_effect = jwt.ExpiredSignatureError('Token expired')
        
        with pytest.raises(Exception) as exc_info:
            lambda_handler(api_gateway_event, None)
        
        assert str(exc_info.value) == 'Unauthorized'

    @patch('handler.validate_token')
    @patch('handler.extract_token')
    def test_lambda_handler_invalid_signature(self, mock_extract_token, mock_validate_token, mock_env, api_gateway_event):
        """Test authorization with invalid signature"""
        mock_extract_token.return_value = 'invalid-token'
        mock_validate_token.side_effect = jwt.InvalidSignatureError('Invalid signature')
        
        with pytest.raises(Exception) as exc_info:
            lambda_handler(api_gateway_event, None)
        
        assert str(exc_info.value) == 'Unauthorized'

    @patch('handler.extract_token')
    def test_lambda_handler_missing_configuration(self, mock_extract_token, api_gateway_event):
        """Test authorization with missing configuration"""
        with patch.dict(os.environ, {}, clear=True):
            mock_extract_token.return_value = 'valid-token'
            
            with pytest.raises(Exception) as exc_info:
                lambda_handler(api_gateway_event, None)
            
            assert str(exc_info.value) == 'Unauthorized'

    @patch('handler.validate_token')
    @patch('handler.extract_token')
    def test_lambda_handler_missing_sub_claim(self, mock_extract_token, mock_validate_token, mock_env, api_gateway_event, valid_token_claims):
        """Test authorization with missing sub claim"""
        mock_extract_token.return_value = 'valid-token'
        claims = valid_token_claims.copy()
        del claims['sub']
        mock_validate_token.return_value = claims
        
        with pytest.raises(Exception) as exc_info:
            lambda_handler(api_gateway_event, None)
        
        assert str(exc_info.value) == 'Unauthorized'
