# Task 10: Create Lambda Function and Deployment Configuration

## Task Description

Created the Lambda function handler and deployment configuration for the translation broadcasting pipeline, including environment variables, IAM permissions, and Lambda layer for shared code.

## Task Instructions

From tasks.md:
- 10.1 Set up Lambda function structure (runtime Python 3.11, memory 1024 MB, timeout 30 seconds)
- 10.2 Configure environment variables (table names, configuration parameters)
- 10.3 Set up IAM permissions (DynamoDB, Translate, Polly, API Gateway, CloudWatch)
- 10.4 Create deployment package (Lambda layer with shared code)

## Task Tests

All tests passing:

```bash
$ python -m pytest tests/test_infrastructure.py -v
tests/test_infrastructure.py::test_stack_synthesizes PASSED
tests/test_infrastructure.py::test_sessions_table_created PASSED
tests/test_infrastructure.py::test_connections_table_with_gsi PASSED
tests/test_infrastructure.py::test_cached_translations_table_with_ttl PASSED
tests/test_infrastructure.py::test_cloudwatch_alarms_created PASSED
tests/test_infrastructure.py::test_sns_topic_created PASSED
tests/test_infrastructure.py::test_stack_outputs PASSED

7 passed, 158 warnings in 3.50s
```

All unit tests continue to pass:

```bash
$ python -m pytest tests/unit/ -v
147 tests passed
```

## Task Solution

### 1. Lambda Function Handler

Created `lambda/translation_processor/handler.py` with:

**Main Handler Function**:
- Validates required event fields (sessionId, sourceLanguage, transcriptText, emotionDynamics)
- Creates EmotionDynamics object from event data
- Processes transcript through orchestrator using asyncio.run()
- Emits CloudWatch metrics for monitoring
- Returns success/error response with detailed metrics

**Event Format**:
```json
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
```

**Response Format**:
```json
{
  "success": true,
  "languagesProcessed": ["es", "fr", "de"],
  "languagesFailed": [],
  "cacheHitRate": 0.67,
  "broadcastSuccessRate": 0.98,
  "durationMs": 2170.5,
  "listenerCount": 15
}
```

**Service Initialization**:
- All AWS clients initialized once per container (cold start optimization)
- Services reused across invocations
- Orchestrator configured with all dependencies

### 2. Environment Variables

Configured in CDK stack:

| Variable | Description | Default |
|----------|-------------|---------|
| `SESSIONS_TABLE_NAME` | DynamoDB Sessions table | Required |
| `CONNECTIONS_TABLE_NAME` | DynamoDB Connections table | Required |
| `CACHED_TRANSLATIONS_TABLE_NAME` | DynamoDB CachedTranslations table | Required |
| `API_GATEWAY_ENDPOINT` | WebSocket API endpoint | Required |
| `MAX_CONCURRENT_BROADCASTS` | Concurrent broadcast limit | 100 |
| `CACHE_TTL_SECONDS` | Translation cache TTL | 3600 |
| `MAX_CACHE_ENTRIES` | Max cache entries before LRU | 10000 |

### 3. IAM Permissions

Created comprehensive IAM role with permissions for:

**DynamoDB**:
- GetItem, PutItem, Query, UpdateItem, DeleteItem on all tables
- Query permission on Connections table GSI

**AWS Services**:
- AWS Translate: TranslateText
- AWS Polly: SynthesizeSpeech
- API Gateway: ManageConnections
- CloudWatch: PutMetricData

**Managed Policies**:
- AWSLambdaBasicExecutionRole (CloudWatch Logs)

### 4. Lambda Layer

Created Lambda layer for shared code:

**Layer Structure**:
```
shared/
├── data_access/
│   ├── atomic_counter.py
│   ├── connections_repository.py
│   └── __init__.py
├── services/
│   ├── translation_cache_manager.py
│   ├── parallel_translation_service.py
│   ├── ssml_generator.py
│   ├── parallel_synthesis_service.py
│   ├── broadcast_handler.py
│   ├── audio_buffer_manager.py
│   └── translation_pipeline_orchestrator.py
└── __init__.py
```

**Layer Configuration**:
- Compatible runtime: Python 3.11
- Path resolution: Handles both infrastructure deployment and test execution
- Reusable across multiple Lambda functions

### 5. ConnectionsRepository

Created `shared/data_access/connections_repository.py` for querying connections:

**Methods**:
- `get_unique_target_languages(session_id)`: Query GSI for unique languages
- `get_listeners_for_language(session_id, target_language)`: Query GSI for connection IDs
- `remove_connection(connection_id)`: Remove stale connections

**GSI Usage**:
- Index: sessionId-targetLanguage-index
- Partition key: sessionId
- Sort key: targetLanguage
- Filter: role = "listener"
- Projection: Specific fields only (optimization)

### 6. CloudWatch Metrics

Handler emits metrics to `TranslationPipeline` namespace:

- `CacheHitRate`: Translation cache hit rate (%)
- `BroadcastSuccessRate`: Broadcast success rate (%)
- `ProcessingDuration`: Total processing time (ms)
- `LanguagesProcessed`: Number of languages processed
- `FailedLanguagesCount`: Number of failed languages
- `ListenerCount`: Number of active listeners

### 7. CDK Stack Updates

Updated `TranslationPipelineStack` with:

**New Methods**:
- `_create_shared_layer()`: Creates Lambda layer with shared code
- `_create_translation_processor_function()`: Creates Lambda function with full configuration

**Path Resolution**:
- Uses `os.path.join()` for cross-platform compatibility
- Resolves paths relative to stack file location
- Works in both deployment and test contexts

**Outputs**:
- TranslationProcessorFunctionName
- TranslationProcessorFunctionArn
- SharedLayerArn

### 8. Documentation

Created comprehensive README at `lambda/translation_processor/README.md`:

**Sections**:
- Overview and architecture
- Event/response formats
- Environment variables
- IAM permissions
- Configuration (memory, timeout, runtime)
- CloudWatch metrics
- Deployment instructions (CDK and manual)
- Testing instructions
- Monitoring and troubleshooting
- Performance optimization
- Cost optimization

## Key Implementation Decisions

1. **Cold Start Optimization**: Initialize all AWS clients and services outside the handler function for reuse across invocations

2. **Async Execution**: Use `asyncio.run()` to execute the async orchestrator from the synchronous Lambda handler

3. **Path Resolution**: Use `os.path.join()` with `__file__` for reliable path resolution in both deployment and test contexts

4. **Error Handling**: Comprehensive try-except blocks with detailed error messages and proper HTTP status codes

5. **Metrics Emission**: Emit metrics after processing completes, with error handling to prevent metric failures from affecting the response

6. **Lambda Layer**: Package shared code in a layer for reusability and to keep function package size small

## Files Created

- `lambda/__init__.py`
- `lambda/translation_processor/__init__.py`
- `lambda/translation_processor/handler.py`
- `lambda/translation_processor/requirements.txt`
- `lambda/translation_processor/README.md`
- `shared/data_access/__init__.py`
- `shared/data_access/connections_repository.py`

## Files Modified

- `infrastructure/stacks/translation_pipeline_stack.py` - Added Lambda layer and function creation

## Requirements Addressed

- **Requirement 10.1**: Lambda function structure with Python 3.11, 1024 MB memory, 30-second timeout
- **Requirement 10.2**: Environment variables for all table names and configuration parameters
- **Requirement 10.3**: IAM permissions for DynamoDB, Translate, Polly, API Gateway, CloudWatch
- **Requirement 10.4**: Deployment package with Lambda layer for shared code

## Next Steps

Task 10 is complete. Ready to proceed with:
- Task 11: Set up monitoring and alerting (CloudWatch dashboard)
- Task 12: Create integration tests (end-to-end pipeline testing)
