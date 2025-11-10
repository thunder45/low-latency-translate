"""
Lambda Authorizer for validating JWT tokens from AWS Cognito.
"""
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Validate JWT token and return IAM policy.
    
    Args:
        event: Lambda authorizer event with token in queryStringParameters
        context: Lambda context
        
    Returns:
        IAM policy document (Allow/Deny)
    """
    logger.info("Authorizer invoked")
    
    # Implementation will be added in subsequent tasks
    raise Exception('Unauthorized')
