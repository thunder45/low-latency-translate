# Translation Broadcasting Pipeline Infrastructure

This directory contains AWS CDK infrastructure code for the Translation Broadcasting Pipeline component.

## Overview

The infrastructure includes:

1. **DynamoDB Tables**:
   - **Sessions**: Tracks active sessions with atomic listenerCount counter
   - **Connections**: Stores connection metadata with sessionId-targetLanguage GSI for efficient language-based queries
   - **CachedTranslations**: Caches translation results with TTL for cost optimization

2. **CloudWatch Alarms**:
   - Cache hit rate monitoring
   - Broadcast success rate monitoring
   - Buffer overflow detection
   - Failed languages tracking

3. **SNS Topics**:
   - Alarm notifications

## Prerequisites

- Python 3.11+
- AWS CDK CLI (`npm install -g aws-cdk`)
- AWS credentials configured
- AWS account and region set in config

## Setup

1. Install dependencies:
```bash
cd translation-pipeline/infrastructure
pip install -r requirements.txt
```

2. Configure environment:
```bash
# Edit config/dev.json with your AWS account and region
{
  "account": "123456789012",
  "region": "us-east-1",
  "alarmEmail": "your-email@example.com"
}
```

3. Bootstrap CDK (first time only):
```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

## Deployment

### Deploy to Development

```bash
cdk deploy --context env=dev
```

### Deploy to Production

```bash
cdk deploy --context env=prod
```

### View Changes Before Deployment

```bash
cdk diff --context env=dev
```

### Destroy Stack

```bash
cdk destroy --context env=dev
```

## DynamoDB Table Schemas

### Sessions Table

```python
{
    "sessionId": "golden-eagle-427",  # Partition Key
    "speakerConnectionId": "L0SM9cOFvHcCIhw=",
    "sourceLanguage": "en",
    "listenerCount": 15,  # Atomic counter
    "isActive": True,
    "createdAt": 1699500000000,
    "expiresAt": 1699510800000  # TTL
}
```

### Connections Table

```python
{
    "connectionId": "K3Rx8bNEuGdDJkx=",  # Partition Key
    "sessionId": "golden-eagle-427",
    "targetLanguage": "es",
    "role": "listener",
    "connectedAt": 1699500120000,
    "ttl": 1699510800
}
```

**Global Secondary Index**: `sessionId-targetLanguage-index`
- Partition Key: `sessionId`
- Sort Key: `targetLanguage`
- Projection: ALL

### CachedTranslations Table

```python
{
    "cacheKey": "en:es:3f7b2a1c9d8e5f4a",  # Partition Key
    "sourceLanguage": "en",
    "targetLanguage": "es",
    "sourceText": "Hello everyone, this is important news.",
    "translatedText": "Hola a todos, estas son noticias importantes.",
    "createdAt": 1699500000000,
    "accessCount": 5,
    "lastAccessedAt": 1699500300000,
    "ttl": 1699503600  # 1 hour TTL
}
```

## Query Patterns

### Get Unique Target Languages

```python
response = dynamodb.query(
    TableName='Connections',
    IndexName='sessionId-targetLanguage-index',
    KeyConditionExpression='sessionId = :sid',
    FilterExpression='#role = :role',
    ExpressionAttributeNames={'#role': 'role'},
    ExpressionAttributeValues={
        ':sid': 'golden-eagle-427',
        ':role': 'listener'
    }
)

# Extract unique languages
languages = set(item['targetLanguage'] for item in response['Items'])
```

### Get Listeners for Specific Language

```python
response = dynamodb.query(
    TableName='Connections',
    IndexName='sessionId-targetLanguage-index',
    KeyConditionExpression='sessionId = :sid AND targetLanguage = :lang',
    ExpressionAttributeValues={
        ':sid': 'golden-eagle-427',
        ':lang': 'es'
    }
)

connection_ids = [item['connectionId'] for item in response['Items']]
```

### Atomic Counter Operations

```python
# Increment listener count
dynamodb.update_item(
    TableName='Sessions',
    Key={'sessionId': 'golden-eagle-427'},
    UpdateExpression='ADD listenerCount :inc',
    ExpressionAttributeValues={':inc': 1}
)

# Decrement listener count
dynamodb.update_item(
    TableName='Sessions',
    Key={'sessionId': 'golden-eagle-427'},
    UpdateExpression='ADD listenerCount :dec',
    ExpressionAttributeValues={':dec': -1}
)
```

## CloudWatch Alarms

The stack creates the following alarms:

1. **Cache Hit Rate Low** (< 30%)
   - Indicates cache effectiveness is poor
   - May need to adjust cache TTL or size

2. **Broadcast Success Rate Low** (< 95%)
   - Indicates connection issues
   - Check API Gateway throttling and connection health

3. **Buffer Overflow Rate High** (> 5%)
   - Indicates latency issues
   - Check broadcast performance and network conditions

4. **Failed Languages High** (> 10%)
   - Indicates AWS Translate or Polly issues
   - Check service quotas and error logs

## Monitoring

View CloudWatch metrics in the AWS Console:

**Namespace**: `TranslationPipeline`

**Metrics**:
- `CacheHitRate`: Percentage of cache hits
- `CacheSize`: Current number of cached entries
- `CacheEvictions`: Number of LRU evictions
- `BroadcastSuccessRate`: Percentage of successful broadcasts
- `BroadcastLatency`: Time to broadcast to all listeners
- `BufferOverflowRate`: Percentage of buffer overflows
- `FailedLanguagesCount`: Number of languages that failed processing

## Cost Optimization

The infrastructure is configured for cost optimization:

1. **On-Demand Billing**: DynamoDB tables use PAY_PER_REQUEST mode
2. **TTL Enabled**: Automatic cleanup of expired data
3. **Point-in-Time Recovery**: Enabled only for production
4. **Removal Policy**: DESTROY for dev, RETAIN for prod

## Troubleshooting

### CDK Deployment Fails

```bash
# Check CDK version
cdk --version

# Update CDK
npm update -g aws-cdk

# Clear CDK cache
rm -rf cdk.out
```

### Table Already Exists

If tables already exist from a previous deployment:

```bash
# Delete tables manually in AWS Console
# Or use AWS CLI
aws dynamodb delete-table --table-name Sessions-dev
aws dynamodb delete-table --table-name Connections-dev
aws dynamodb delete-table --table-name CachedTranslations-dev
```

### Permission Denied

Ensure your AWS credentials have the following permissions:
- DynamoDB: CreateTable, DeleteTable, DescribeTable
- CloudWatch: PutMetricAlarm, DeleteAlarms
- SNS: CreateTopic, Subscribe
- IAM: CreateRole, AttachRolePolicy

## References

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [Global Secondary Indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html)
- [DynamoDB TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)
