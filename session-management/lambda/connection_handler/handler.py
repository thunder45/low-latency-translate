"""
WebSocket Connection Handler for $connect events.
Handles both speaker session creation and listener joining.
"""
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Handle WebSocket $connect event.
    
    Args:
        event: API Gateway WebSocket $connect event
        context: Lambda context
        
    Returns:
        Response with status code and body
    """
    logger.info(f"Connection handler invoked: {json.dumps(event)}")
    
    # Implementation will be added in subsequent tasks
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Connected'})
    }
