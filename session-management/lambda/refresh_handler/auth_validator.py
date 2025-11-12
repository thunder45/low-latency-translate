"""
Application-level JWT validation for refresh handler.

Since WebSocket custom routes don't support API Gateway authorizers,
we validate JWT tokens at the application level.
"""
import json
import logging
import os
import time
import base64
from urllib.request import urlopen
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Cache for Cognito public keys
_cognito_keys_cache = {}
_cache_timestamp = 0
CACHE_DURATION = 3600  # 1 hour


def validate_speaker_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate JWT token for speaker authentication.
    
    Args:
        token: JWT token string
        
    Returns:
        Claims dict if valid, None otherwise
    """
    if not token:
        logger.warning("No token provided")
        return None
    
    # Validate JWT format
    if token.count('.') != 2:
        logger.warning("Invalid JWT format")
        return None
    
    try:
        # Parse token
        header_b64, payload_b64, signature_b64 = token.split('.')
        
        # Decode header
        header = decode_base64_url(header_b64)
        header_data = json.loads(header)
        
        # Get key ID
        kid = header_data.get('kid')
        if not kid:
            logger.warning("Missing key ID in JWT header")
            return None
        
        # Get Cognito public keys
        public_keys = get_cognito_public_keys()
        if kid not in public_keys:
            logger.warning(f"Unknown key ID: {kid}")
            return None
        
        # 🔒 CRITICAL: Verify JWT signature with RSA public key
        public_key_data = public_keys[kid]
        if not verify_jwt_signature(header_b64, payload_b64, signature_b64, public_key_data):
            logger.warning("JWT signature verification failed")
            return None
        
        # Decode and validate payload
        payload = decode_base64_url(payload_b64)
        claims = json.loads(payload)
        
        # Validate claims
        if not validate_claims(claims):
            return None
        
        logger.info(f"Token validated for user {claims.get('sub', '')[:8]}... (signature verified)")
        return claims
        
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return None


def validate_claims(claims: Dict[str, Any]) -> bool:
    """
    Validate JWT claims.
    
    Args:
        claims: JWT claims
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check required fields
        if not claims.get('sub'):
            logger.warning("Missing 'sub' claim")
            return False
        
        # Check expiration
        exp = claims.get('exp', 0)
        current_time = int(time.time())
        
        if exp <= current_time:
            logger.warning(f"Token expired: {exp} <= {current_time}")
            return False
        
        # Check issuer (Cognito)
        expected_issuer = f"https://cognito-idp.{os.environ.get('REGION', 'us-east-1')}.amazonaws.com/{os.environ.get('USER_POOL_ID', '')}"
        if claims.get('iss') != expected_issuer:
            logger.warning(f"Invalid issuer: {claims.get('iss')}")
            return False
        
        # Check audience (client ID)
        expected_audience = os.environ.get('CLIENT_ID', '')
        if expected_audience and claims.get('aud') != expected_audience:
            logger.warning(f"Invalid audience: {claims.get('aud')}")
            return False
        
        # Check token use
        if claims.get('token_use') != 'id':
            logger.warning(f"Invalid token use: {claims.get('token_use')}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Claims validation error: {e}")
        return False


def get_cognito_public_keys() -> Dict[str, Any]:
    """
    Get Cognito public keys from JWKS endpoint with caching.
    
    Returns:
        Dictionary mapping key ID to key data
    """
    global _cognito_keys_cache, _cache_timestamp
    
    current_time = int(time.time())
    
    # Check cache
    if _cognito_keys_cache and (current_time - _cache_timestamp) < CACHE_DURATION:
        return _cognito_keys_cache
    
    try:
        # Fetch keys from Cognito
        region = os.environ.get('REGION', 'us-east-1')
        user_pool_id = os.environ.get('USER_POOL_ID', '')
        
        if not user_pool_id:
            logger.error("USER_POOL_ID environment variable not set")
            return {}
        
        jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        
        with urlopen(jwks_url) as response:
            jwks_data = json.loads(response.read().decode('utf-8'))
        
        # Convert to dict keyed by kid
        keys = {}
        for key in jwks_data.get('keys', []):
            kid = key.get('kid')
            if kid:
                keys[kid] = key
        
        # Update cache
        _cognito_keys_cache = keys
        _cache_timestamp = current_time
        
        logger.info(f"Loaded {len(keys)} Cognito public keys")
        return keys
        
    except Exception as e:
        logger.error(f"Failed to fetch Cognito public keys: {e}")
        return {}


def verify_jwt_signature(header_b64: str, payload_b64: str, signature_b64: str, public_key_data: Dict[str, Any]) -> bool:
    """
    Verify JWT signature using RSA public key.
    
    Args:
        header_b64: Base64-encoded JWT header
        payload_b64: Base64-encoded JWT payload  
        signature_b64: Base64-encoded JWT signature
        public_key_data: Public key data from Cognito JWKS
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        import cryptography.exceptions
        
        # Extract RSA key components
        n = int.from_bytes(decode_base64_url(public_key_data['n']), 'big')
        e = int.from_bytes(decode_base64_url(public_key_data['e']), 'big')
        
        # Reconstruct RSA public key
        public_numbers = rsa.RSAPublicNumbers(e, n)
        public_key = public_numbers.public_key()
        
        # Create message to verify (header.payload)
        message = f"{header_b64}.{payload_b64}".encode('utf-8')
        
        # Decode signature
        signature = decode_base64_url(signature_b64)
        
        # Verify signature
        try:
            public_key.verify(
                signature,
                message,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except cryptography.exceptions.InvalidSignature:
            logger.warning("Invalid JWT signature")
            return False
            
    except ImportError:
        logger.error("cryptography library not available - signature verification skipped")
        return False  # Fail secure if crypto not available
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


def decode_base64_url(data: str) -> bytes:
    """
    Decode base64 URL-encoded data with padding.
    
    Args:
        data: Base64 URL-encoded string
        
    Returns:
        Decoded bytes
    """
    # Add padding if needed
    data += '=' * (4 - len(data) % 4)
    return base64.urlsafe_b64decode(data)
