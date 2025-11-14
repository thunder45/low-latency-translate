"""
Lambda handler for translation broadcasting pipeline.

This Lambda function processes transcribed text through the translation pipeline:
1. Checks listener count (skip if 0)
2. Discovers target languages
3. Translates text to all languages (parallel, with caching)
4. Generates SSML with emotion dynamics
5. Synthesizes audio (parallel)
6. Broadcasts to all listeners per language

Environment Variables:
    SESSIONS_TABLE_NAME: DynamoDB Sessions table name
    CONNECTIONS_TABLE_NAME: DynamoDB Connections table name
    CACHED_TRANSLATIONS_TABLE_NAME: DynamoDB CachedTranslations table name
    MAX_CONCURRENT_BROADCASTS: Maximum concurrent broadcast connections (default: 100)
    CACHE_TTL_SECONDS: Translation cache TTL in seconds (default: 3600)
    MAX_CACHE_ENTRIES: Maximum cache entries before LRU eviction (default: 10000)
    API_GATEWAY_ENDPOINT: API Gateway WebSocket endpoint for broadcasting
"""

import json
import logging
import os
import sys
from typing import Dict, Any

# Add shared directory to path for imports
sys.path.insert(0, '/opt/python')  # Lambda layer path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import boto3

from shared.data_access.atomic_counter import AtomicCounter
from shared.data_access.connections_repository import ConnectionsRepository
from shared.services.translation_cache_manager import TranslationCacheManager
from shared.services.parallel_translation_service import ParallelTranslationService
from shared.services.ssml_generator import SSMLGenerator
from shared.services.parallel_synthesis_service import ParallelSynthesisService
from shared.services.broadcast_handler import BroadcastHandler
from shared.services.translation_pipeline_orchestrator import (
    TranslationPipelineOrchestrator,
    EmotionDynamics
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SESSIONS_TABLE_NAME = os.environ['SESSIONS_TABLE_NAME']
CONNECTIONS_TABLE_NAME = os.environ['CONNECTIONS_TABLE_NAME']
CACHED_TRANSLATIONS_TABLE_NAME = os.environ['CACHED_TRANSLATIONS_TABLE_NAME']
MAX_CONCURRENT_BROADCASTS = int(os.environ.get('MAX_CONCURRENT_BROADCASTS', '100'))
CACHE_TTL_SECONDS = int(os.environ.get('CACHE_TTL_SECONDS', '3600'))
MAX_CACHE_ENTRIES = int(os.environ.get('MAX_CACHE_ENTRIES', '10000'))
API_GATEWAY_ENDPOINT = os.environ['API_GATEWAY_ENDPOINT']

# AWS clients (initialized once per container)
dynamodb_client = boto3.client('dynamodb')
translate_client = boto3.client('translate')
polly_client = boto3.client('polly')
apigateway_client = boto3.client(
    'apigatewaymanagementapi',
    endpoint_url=API_GATEWAY_ENDPOINT
)
cloudwatch_client = boto3.client('cloudwatch')

# Initialize services (reused across invocations)
atomic_counter = AtomicCounter(
    table_name=SESSIONS_TABLE_NAME,
    dynamodb_client=dynamodb_client
)

connections_repository = ConnectionsRepository(
    table_name=CONNECTIONS_TABLE_NAME,
    dynamodb_client=dynamodb_client
)

translation_cache_manager = TranslationCacheManager(
    table_name=CACHED_TRANSLATIONS_TABLE_NAME,
    dynamodb_client=dynamodb_client,
    ttl_seconds=CACHE_TTL_SECONDS,
    max_entries=MAX_CACHE_ENTRIES,
    cloudwatch_client=cloudwatch_client
)

translation_service = ParallelTranslationService(
    translate_client=translate_client,
    cache_manager=translation_cache_manager
)

ssml_generator = SSMLGenerator()

synthesis_service = ParallelSynthesisService(
    polly_client=polly_client
)

broadcast_handler = BroadcastHandler(
    connections_repository=connections_repository,
    apigateway_client=apigateway_client,
    max_concurrent=MAX_CONCURRENT_BROADCASTS
)

# Initialize orchestrator
orchestrator = TranslationPipelineOrchestrator(
    atomic_counter=atomic_counter,
    connections_repository=connections_repository,
    translation_service=translation_service,
    ssml_generator=ssml_generator,
    synthesis_service=synthesis_service,
    broadcast_handler=broadcast_handler
)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda entry point for translation broadcasting pipeline.
    
    Expected event format:
    {
        "sessionId": "golden-eagle-427",
        "sourceLanguage": "en",
        "transcriptText": "Hello everyone, this is important news.",
        "emotionDynamics": {
            "emotion": "happy",
            "intensity": 0.8,
            "rateWpm": 150,
            "volumeLevel": "normal"
        }
    }
    
    Args:
        event: Lambda event containing transcript and session info
        context: Lambda context object
        
    Returns:
        Response dict with statusCode and body
    """
    try:
        logger.info(f"Processing translation pipeline event: {json.dumps(event)}")
        
        # Validate required fields
        required_fields = ['sessionId', 'sourceLanguage', 'transcriptText', 'emotionDynamics']
        for field in required_fields:
            if field not in event:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'error': f'Missing required field: {field}'
                    })
                }
        
        # Extract event data
        session_id = event['sessionId']
        source_language = event['sourceLanguage']
        transcript_text = event['transcriptText']
        emotion_data = event['emotionDynamics']
        
        # Create EmotionDynamics object
        emotion_dynamics = EmotionDynamics(
            emotion=emotion_data.get('emotion', 'neutral'),
            intensity=emotion_data.get('intensity', 0.5),
            rate_wpm=emotion_data.get('rateWpm', 150),
            volume_level=emotion_data.get('volumeLevel', 'normal')
        )
        
        # Process through pipeline
        import asyncio
        result = asyncio.run(
            orchestrator.process_transcript(
                session_id=session_id,
                source_language=source_language,
                transcript_text=transcript_text,
                emotion_dynamics=emotion_dynamics
            )
        )
        
        # Emit CloudWatch metrics
        _emit_metrics(result)
        
        # Return response
        if result.success:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'languagesProcessed': result.languages_processed,
                    'languagesFailed': result.languages_failed,
                    'cacheHitRate': result.cache_hit_rate,
                    'broadcastSuccessRate': result.broadcast_success_rate,
                    'durationMs': result.total_duration_ms,
                    'listenerCount': result.listener_count
                })
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'success': False,
                    'error': result.error_message,
                    'languagesFailed': result.languages_failed
                })
            }
            
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }


def _emit_metrics(result):
    """
    Emit CloudWatch metrics for pipeline processing.
    
    Args:
        result: ProcessingResult object
    """
    try:
        metrics = []
        
        # Cache hit rate
        if result.cache_hit_rate >= 0:
            metrics.append({
                'MetricName': 'CacheHitRate',
                'Value': result.cache_hit_rate * 100,  # Convert to percentage
                'Unit': 'Percent'
            })
        
        # Broadcast success rate
        if result.broadcast_success_rate >= 0:
            metrics.append({
                'MetricName': 'BroadcastSuccessRate',
                'Value': result.broadcast_success_rate * 100,  # Convert to percentage
                'Unit': 'Percent'
            })
        
        # Processing duration
        metrics.append({
            'MetricName': 'ProcessingDuration',
            'Value': result.total_duration_ms,
            'Unit': 'Milliseconds'
        })
        
        # Languages processed
        metrics.append({
            'MetricName': 'LanguagesProcessed',
            'Value': len(result.languages_processed),
            'Unit': 'Count'
        })
        
        # Failed languages
        if result.languages_failed:
            metrics.append({
                'MetricName': 'FailedLanguagesCount',
                'Value': len(result.languages_failed),
                'Unit': 'Count'
            })
        
        # Listener count
        metrics.append({
            'MetricName': 'ListenerCount',
            'Value': result.listener_count,
            'Unit': 'Count'
        })
        
        # Put metrics to CloudWatch
        if metrics:
            cloudwatch_client.put_metric_data(
                Namespace='TranslationPipeline',
                MetricData=metrics
            )
            
    except Exception as e:
        logger.error(f"Failed to emit CloudWatch metrics: {e}", exc_info=True)
