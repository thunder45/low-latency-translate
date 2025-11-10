"""
Lambda Authorizer for WebSocket API Gateway.

This module validates JWT tokens from AWS Cognito and generates IAM policies
for speaker connections. It implements caching of Cognito public keys for
performance optimization.

Requirements: 7, 19
"""

import json
import logging
import os
import time
from functools import lru_cache
from typing import Dict, Any, Optional

import jwt
import requests
from jwt.algorithms import RSAAlgorithm

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Environment variables
REGION = os.environ.get('REGION', 'us-east-1')
USER_POOL_ID = os.environ.get('USER_POOL_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')


class AuthorizationError(Exception):
    """Custom exception for authorization failures."""
    pass


@lru_cache(maxsize=1)
def get_cognito_public_keys() -> Dict[str, Any]:
    """
    Fetch and cache Cognito public keys from JWKS endpoint.
    
    The public keys are cached for the lifetime of the Lambda container
    to minimize external API calls and improve performance.
    
    Returns:
        Dict containing the JWKS keys
        
    Raises:
        AuthorizationError: If unable to fetch public keys
    """
    jwks_url = f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json'
    
    try:
        logger.info(f'Fetching Cognito public keys from {jwks_url}')
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()
        
        jwks = response.json()
        logger.info(f'Successfully fetched {len(jwks.get("keys", []))} public keys')
        return jwks
        
    except requests.RequestException as e:
        logger.error(f'Failed to fetch Cognito public keys: {str(e)}')
        raise AuthorizationError('Unable to fetch public keys')


def get_public_key_for_token(token: str) -> Optional[str]:
    """
    Extract the public key for a given JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Public key in PEM format, or None if not found
        
    Raises:
        AuthorizationError: If token header is invalid
    """
    try:
        # Decode header without verification to get key ID
        header = jwt.get_unverified_header(token)
        kid = header.get('kid')
        
        if not kid:
            raise AuthorizationError('Token missing key ID (kid)')
        
        # Get public keys from Cognito
        jwks = get_cognito_public_keys()
        
        # Find matching key
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                # Convert JWK to PEM format
                public_key = RSAAlgorithm.from_jwk(json.dumps(key))
                return public_key
        
        logger.warning(f'Public key not found for kid: {kid}')
        return None
        
    except jwt.DecodeError as e:
        logger.error(f'Failed to decode token header: {str(e)}')
        raise AuthorizationError('Invalid token format')


def validate_jwt_token(token: str) -> Dict[str, Any]:
    """
    Validate JWT token signature and claims.
    
    Validates:
    - Token signature using Cognito public key
    - Token expiration
    - Audience claim (client ID)
    - Issuer claim (Cognito user pool)
    
    Args:
        token: JWT token string
        
    Returns:
        Dict containing decoded token claims
        
    Raises:
        AuthorizationError: If token validation fails
    """
    try:
        # Get public key for token
        public_key = get_public_key_for_token(token)
        
        if not public_key:
            raise AuthorizationError('Public key not found')
        
        # Verify and decode token
        issuer = f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}'
        
        claims = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience=CLIENT_ID,
            issuer=issuer,
            options={
                'verify_signature': True,
                'verify_exp': True,
                'verify_aud': True,
                'verify_iss': True
            }
        )
        
        logger.info(f'Token validated successfully for user: {claims.get("sub")}')
        return claims
        
    except jwt.ExpiredSignatureError:
        logger.warning('Token has expired')
        raise AuthorizationError('Token expired')
        
    except jwt.InvalidAudienceError:
        logger.warning(f'Invalid audience. Expected: {CLIENT_ID}')
        raise AuthorizationError('Invalid token audience')
        
    except jwt.InvalidIssuerError:
        logger.warning(f'Invalid issuer. Expected: {issuer}')
        raise AuthorizationError('Invalid token issuer')
        
    except jwt.InvalidSignatureError:
        logger.warning('Invalid token signature')
        raise AuthorizationError('Invalid token signature')
        
    except jwt.DecodeError as e:
        logger.error(f'Failed to decode token: {str(e)}')
        raise AuthorizationError('Invalid token format')
        
    except Exception as e:
        logger.error(f'Unexpected error during token validation: {str(e)}', exc_info=True)
        raise AuthorizationError('Token validation failed')


def generate_allow_policy(principal_id: str, method_arn: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate IAM Allow policy for valid tokens.
    
    Args:
        principal_id: User identifier (Cognito sub claim)
        method_arn: API Gateway method ARN
        context: Additional context to pass to Lambda functions
        
    Returns:
        IAM policy document with Allow effect
    """
    return {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': 'Allow',
                    'Resource': method_arn
                }
            ]
        },
        'context': context
    }


def generate_deny_policy(principal_id: str, method_arn: str) -> Dict[str, Any]:
    """
    Generate IAM Deny policy for invalid tokens.
    
    Args:
        principal_id: User identifier or 'unauthorized'
        method_arn: API Gateway method ARN
        
    Returns:
        IAM policy document with Deny effect
    """
    return {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': 'Deny',
                    'Resource': method_arn
                }
            ]
        }
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda Authorizer handler for WebSocket API Gateway.
    
    Validates JWT tokens from query string parameters and generates
    IAM policies for speaker connections.
    
    Args:
        event: API Gateway authorizer event
        context: Lambda context object
        
    Returns:
        IAM policy document (Allow or Deny)
    """
    # Extract token from query string parameters
    query_params = event.get('queryStringParameters', {}) or {}
    token = query_params.get('token')
    method_arn = event.get('methodArn')
    
    # Log request (without sensitive data)
    request_id = context.request_id if context else 'unknown'
    logger.info(f'Authorization request: requestId={request_id}, hasToken={bool(token)}')
    
    try:
        # Validate token presence
        if not token:
            logger.warning('Missing token in request')
            raise AuthorizationError('Missing token')
        
        # Validate JWT token
        claims = validate_jwt_token(token)
        
        # Extract user information
        user_id = claims.get('sub')
        email = claims.get('email', '')
        
        # Generate Allow policy with user context
        policy = generate_allow_policy(
            principal_id=user_id,
            method_arn=method_arn,
            context={
                'userId': user_id,
                'email': email
            }
        )
        
        logger.info(f'Authorization successful for user: {user_id}')
        return policy
        
    except AuthorizationError as e:
        # Log authorization failure
        logger.error(
            f'Authorization failed: {str(e)}',
            extra={
                'requestId': request_id,
                'errorType': 'AuthorizationError',
                'timestamp': int(time.time() * 1000)
            }
        )
        
        # Return Deny policy
        return generate_deny_policy('unauthorized', method_arn)
        
    except Exception as e:
        # Log unexpected errors
        logger.error(
            f'Unexpected authorization error: {str(e)}',
            exc_info=True,
            extra={
                'requestId': request_id,
                'errorType': type(e).__name__,
                'timestamp': int(time.time() * 1000)
            }
        )
        
        # Return Deny policy for any unexpected errors
        return generate_deny_policy('unauthorized', method_arn)
