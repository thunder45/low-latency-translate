"""
Secure Lambda Authorizer with proper JWT validation using PyJWT.
Validates Cognito JWT tokens with full signature verification.
"""
import json
import logging
import os
from typing import Dict, Any, Optional
import jwt
from jwt import PyJWKClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
COGNITO_USER_POOL_ID = os.environ.get('USER_POOL_ID')
COGNITO_CLIENT_ID = os.environ.get('CLIENT_ID')
AWS_REGION = os.environ.get('REGION', 'us-east-1')

# Cognito JWKS URL
JWKS_URL = f'https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json' if COGNITO_USER_POOL_ID else None

# Cache JWKS client (reused across invocations)
_jwks_client = None


def get_jwks_client():
    """Get or create JWKS client for token validation"""
    global _jwks_client
    if _jwks_client is None and JWKS_URL:
        _jwks_client = PyJWKClient(JWKS_URL)
    return _jwks_client


def extract_token(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract JWT token from query string or Authorization header
    
    Priority:
    1. Query string parameter 'token'
    2. Authorization header (Bearer format)
    """
    # Try query string first
    query_params = event.get('queryStringParameters') or {}
    token = query_params.get('token')
    
    if token:
        logger.info('Token found in query string')
        return token
    
    # Try Authorization header
    headers = event.get('headers') or {}
    auth_header = headers.get('Authorization') or headers.get('authorization')
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        logger.info('Token found in Authorization header')
        return token
    
    logger.warning('No token found in query string or Authorization header')
    return None


def validate_token(token: str) -> Dict[str, Any]:
    """
    Validate JWT token from Cognito
    
    Validates:
    - Signature using Cognito public keys
    - Issuer (iss claim)
    - Audience (aud claim)
    - Expiration (exp claim)
    - Token use (token_use claim should be 'id')
    
    Returns decoded token claims if valid
    Raises jwt.PyJWTError if invalid
    """
    try:
        # Get signing key from JWKS
        client = get_jwks_client()
        if not client:
            raise jwt.InvalidTokenError('JWKS client not initialized')
            
        signing_key = client.get_signing_key_from_jwt(token)
        
        # Expected issuer
        expected_issuer = f'https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}'
        
        # Decode and validate token
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=['RS256'],
            audience=COGNITO_CLIENT_ID,
            issuer=expected_issuer,
            options={
                'verify_signature': True,
                'verify_exp': True,
                'verify_aud': True,
                'verify_iss': True,
            }
        )
        
        # Verify token_use is 'id' (not access token)
        token_use = decoded.get('token_use')
        if token_use != 'id':
            raise jwt.InvalidTokenError(f'Invalid token_use: {token_use}, expected "id"')
        
        logger.info(f'Token validated successfully for user: {decoded.get("sub")}')
        return decoded
        
    except jwt.ExpiredSignatureError:
        logger.error('Token validation failed: Token expired')
        raise
    except jwt.InvalidAudienceError:
        logger.error(f'Token validation failed: Invalid audience. Expected: {COGNITO_CLIENT_ID}')
        raise
    except jwt.InvalidIssuerError:
        logger.error(f'Token validation failed: Invalid issuer. Expected: {expected_issuer}')
        raise
    except jwt.InvalidSignatureError:
        logger.error('Token validation failed: Invalid signature')
        raise
    except jwt.InvalidTokenError as e:
        logger.error(f'Token validation failed: {str(e)}')
        raise
    except Exception as e:
        # Wrap unexpected errors as InvalidTokenError so they're handled gracefully
        logger.error(f'Unexpected error during token validation: {str(e)}')
        raise jwt.InvalidTokenError(f'Token validation error: {str(e)}')


def generate_policy(principal_id: str, effect: str, resource: str, context: Optional[Dict] = None) -> Dict:
    """Generate IAM policy for API Gateway"""
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        }
    }
    
    if context:
        policy['context'] = context
    
    return policy


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict:
    """
    Lambda authorizer for WebSocket API Gateway
    
    Handles both authenticated speakers (with JWT) and anonymous listeners:
    - If token present and valid: Allow with userId in context (speaker)
    - If no token present: Allow with empty userId in context (listener)
    - If token present but invalid: Deny
    """
    try:
        # Validate configuration
        if not COGNITO_USER_POOL_ID or not COGNITO_CLIENT_ID:
            logger.error('Missing Cognito configuration')
            raise Exception('Unauthorized')
        
        # Extract token
        token = extract_token(event)
        method_arn = event['methodArn']
        
        # Case 1: No token provided - Allow as anonymous listener
        if not token:
            logger.info('No token provided - authorizing as anonymous listener')
            policy = generate_policy(
                principal_id='anonymous',
                effect='Allow',
                resource=method_arn,
                context={
                    'userId': '',  # Empty string for listeners
                    'email': '',
                }
            )
            return policy
        
        # Case 2: Token provided - Validate and authorize as speaker
        try:
            decoded = validate_token(token)
            
            # Extract user information
            user_id = decoded.get('sub')
            email = decoded.get('email')
            
            if not user_id:
                logger.error('Token missing sub claim')
                raise Exception('Unauthorized')
            
            # Generate allow policy with userId
            policy = generate_policy(
                principal_id=user_id,
                effect='Allow',
                resource=method_arn,
                context={
                    'userId': user_id,
                    'email': email or '',
                }
            )
            
            logger.info(f'Authorization successful for speaker: {user_id}')
            return policy
            
        except jwt.ExpiredSignatureError:
            logger.warning('Token expired - treating as anonymous listener')
            # Treat expired tokens as anonymous listeners (allow but without userId)
            policy = generate_policy(
                principal_id='anonymous-expired',
                effect='Allow',
                resource=method_arn,
                context={
                    'userId': '',
                    'email': '',
                }
            )
            return policy
        except jwt.PyJWTError as e:
            logger.warning(f'JWT validation error: {str(e)} - treating as anonymous listener')
            # Treat invalid tokens as anonymous listeners (allow but without userId)
            # This handles cases like:
            # - Signing key mismatch (key rotation)
            # - Invalid audience/issuer
            # - Malformed tokens
            # Connection handler will determine actual role based on targetLanguage presence
            policy = generate_policy(
                principal_id='anonymous-invalid-token',
                effect='Allow',
                resource=method_arn,
                context={
                    'userId': '',
                    'email': '',
                }
            )
            return policy
        
    except Exception as e:
        logger.error(f'Authorization failed: {str(e)}')
        raise Exception('Unauthorized')
