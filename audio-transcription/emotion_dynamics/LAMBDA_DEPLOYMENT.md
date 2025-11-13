# Lambda Deployment Configuration for Emotion Dynamics

## Overview

This document describes the Lambda deployment configuration for the Emotion Dynamics Detection & SSML Generation component. The Lambda function processes speaker audio to extract paralinguistic features (volume, speaking rate) and generates SSML-enhanced speech via Amazon Polly.

## Lambda Configuration

### Runtime Configuration

```python
Runtime: Python 3.11
Handler: handler.lambda_handler
Memory: 1024 MB
Timeout: 15 seconds
Ephemeral Storage: 1024 MB
Architecture: x86_64
```

### Memory Justification

**1024 MB required for**:
- librosa audio processing library (~300 MB)
- numpy numerical computing (~200 MB)
- Audio buffer storage (~100 MB for 3-second segments)
- Concurrent detector execution (~200 MB)
- Overhead and safety margin (~224 MB)

### Timeout Justification

**15 seconds allows for**:
- Volume detection: <50ms
- Rate detection: <50ms
- SSML generation: <50ms
- Polly synthesis: <800ms
- Retry logic: 3 retries with exponential backoff (~2s)
- Network latency: ~1s
- Safety margin: ~12s

### Ephemeral Storage

**1024 MB for**:
- Temporary audio file storage
- librosa cache files
- Model loading cache

## Environment Variables

### Required Variables

```bash
# AWS Configuration
AWS_REGION=us-east-1

# Polly Configuration
VOICE_ID=Joanna
POLLY_ENGINE=neural
POLLY_OUTPUT_FORMAT=mp3
POLLY_SAMPLE_RATE=24000

# Feature Flags
ENABLE_SSML=true
ENABLE_VOLUME_DETECTION=true
ENABLE_RATE_DETECTION=true
ENABLE_METRICS=true

# Processing Configuration
MIN_STABILITY_THRESHOLD=0.85
MAX_RETRIES=3
RETRY_BASE_DELAY=0.1
RETRY_MAX_DELAY=2.0

# Logging Configuration
LOG_LEVEL=INFO
STRUCTURED_LOGGING=true

# Performance Configuration
AUDIO_SAMPLE_RATE=16000
MAX_AUDIO_DURATION_SECONDS=3
```

### Optional Variables

```bash
# Advanced Configuration
ENABLE_CACHING=true
CACHE_TTL_SECONDS=300
ENABLE_XRAY_TRACING=false

# Threshold Overrides (for testing)
VOLUME_LOUD_THRESHOLD=-10
VOLUME_MEDIUM_THRESHOLD=-20
VOLUME_SOFT_THRESHOLD=-30
RATE_VERY_SLOW_THRESHOLD=100
RATE_SLOW_THRESHOLD=130
RATE_MEDIUM_THRESHOLD=160
RATE_FAST_THRESHOLD=190
```

## Lambda Layer Option

### Why Use Lambda Layers?

Lambda layers reduce deployment package size and improve cold start times by separating heavy dependencies (librosa, numpy) from application code.

### Creating a Lambda Layer

**Option 1: Build Locally (macOS/Linux)**

```bash
# Create layer directory structure
mkdir -p layer/python

# Install dependencies to layer
pip install \
    librosa>=0.10.0 \
    numpy>=1.24.0 \
    soundfile>=0.12.0 \
    -t layer/python

# Create layer zip
cd layer
zip -r ../emotion-dynamics-layer.zip python
cd ..

# Upload to AWS Lambda
aws lambda publish-layer-version \
    --layer-name emotion-dynamics-dependencies \
    --description "librosa, numpy, soundfile for emotion dynamics" \
    --zip-file fileb://emotion-dynamics-layer.zip \
    --compatible-runtimes python3.11 \
    --compatible-architectures x86_64
```

**Option 2: Use Docker (Cross-platform)**

```bash
# Create Dockerfile for layer build
cat > Dockerfile.layer << 'EOF'
FROM public.ecr.aws/lambda/python:3.11

RUN pip install \
    librosa>=0.10.0 \
    numpy>=1.24.0 \
    soundfile>=0.12.0 \
    -t /opt/python

CMD ["echo", "Layer built successfully"]
EOF

# Build layer using Docker
docker build -f Dockerfile.layer -t emotion-layer-builder .

# Extract layer from container
docker create --name temp-layer emotion-layer-builder
docker cp temp-layer:/opt ./layer
docker rm temp-layer

# Create layer zip
cd layer
zip -r ../emotion-dynamics-layer.zip python
cd ..

# Upload to AWS Lambda
aws lambda publish-layer-version \
    --layer-name emotion-dynamics-dependencies \
    --description "librosa, numpy, soundfile for emotion dynamics" \
    --zip-file fileb://emotion-dynamics-layer.zip \
    --compatible-runtimes python3.11 \
    --compatible-architectures x86_64
```

**Option 3: Use Pre-built AWS Lambda Layer (Recommended)**

AWS provides pre-built layers for scientific computing:

```bash
# Use AWS Data Science Layer (includes numpy, scipy)
# Layer ARN: arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python311:1

# You'll still need to create a custom layer for librosa
```

### Using the Layer in CDK

```python
from aws_cdk import aws_lambda as lambda_

# Reference existing layer
emotion_layer = lambda_.LayerVersion.from_layer_version_arn(
    self,
    'EmotionDynamicsLayer',
    layer_version_arn='arn:aws:lambda:us-east-1:123456789012:layer:emotion-dynamics-dependencies:1'
)

# Create Lambda function with layer
function = lambda_.Function(
    self,
    'EmotionDynamicsFunction',
    runtime=lambda_.Runtime.PYTHON_3_11,
    handler='handler.lambda_handler',
    code=lambda_.Code.from_asset('lambda/emotion_dynamics'),
    layers=[emotion_layer],
    memory_size=1024,
    timeout=Duration.seconds(15),
    ephemeral_storage=Size.mebibytes(1024)
)
```

## Deployment Package Structure

### Without Lambda Layer

```
emotion-dynamics-deployment.zip
├── handler.py                          # Lambda entry point
├── emotion_dynamics/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── volume_detector.py
│   │   └── speaking_rate_detector.py
│   ├── generators/
│   │   ├── __init__.py
│   │   └── ssml_generator.py
│   ├── clients/
│   │   ├── __init__.py
│   │   └── polly_client.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── volume_result.py
│   │   ├── rate_result.py
│   │   ├── audio_dynamics.py
│   │   ├── processing_options.py
│   │   └── processing_result.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── configuration.py
│   └── utils/
│       ├── __init__.py
│       ├── metrics.py
│       └── structured_logger.py
└── [dependencies]
    ├── librosa/
    ├── numpy/
    ├── soundfile/
    └── boto3/
```

**Package Size**: ~150-200 MB (exceeds Lambda 50 MB direct upload limit)
**Deployment Method**: Must use S3 upload

### With Lambda Layer

```
emotion-dynamics-deployment.zip (Application Code)
├── handler.py
└── emotion_dynamics/
    └── [application code only]

emotion-dynamics-layer.zip (Dependencies)
└── python/
    ├── librosa/
    ├── numpy/
    ├── soundfile/
    └── [other dependencies]
```

**Application Package Size**: ~5-10 MB
**Layer Package Size**: ~140-180 MB
**Deployment Method**: Direct upload for application, S3 for layer

## CDK Stack Example

```python
from aws_cdk import (
    Stack,
    Duration,
    Size,
    aws_lambda as lambda_,
    aws_iam as iam,
)
from constructs import Construct


class EmotionDynamicsStack(Stack):
    """CDK stack for Emotion Dynamics Lambda function."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Lambda execution role
        lambda_role = self._create_lambda_role()

        # Create Lambda layer (optional)
        emotion_layer = self._create_lambda_layer()

        # Create Lambda function
        emotion_function = self._create_lambda_function(lambda_role, emotion_layer)

    def _create_lambda_role(self) -> iam.Role:
        """Create IAM role with required permissions."""
        role = iam.Role(
            self,
            'EmotionDynamicsLambdaRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            description='Execution role for Emotion Dynamics Lambda'
        )

        # Basic Lambda execution
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                'service-role/AWSLambdaBasicExecutionRole'
            )
        )

        # Polly permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=['polly:SynthesizeSpeech'],
                resources=['*']
            )
        )

        # CloudWatch metrics
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=['cloudwatch:PutMetricData'],
                resources=['*'],
                conditions={
                    'StringEquals': {
                        'cloudwatch:namespace': 'EmotionDynamics'
                    }
                }
            )
        )

        return role

    def _create_lambda_layer(self) -> lambda_.LayerVersion:
        """Create Lambda layer with dependencies."""
        return lambda_.LayerVersion(
            self,
            'EmotionDynamicsLayer',
            code=lambda_.Code.from_asset('layers/emotion-dynamics-layer.zip'),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description='librosa, numpy, soundfile for emotion dynamics',
            layer_version_name='emotion-dynamics-dependencies'
        )

    def _create_lambda_function(
        self,
        role: iam.Role,
        layer: lambda_.LayerVersion
    ) -> lambda_.Function:
        """Create Lambda function."""
        return lambda_.Function(
            self,
            'EmotionDynamicsFunction',
            function_name='emotion-dynamics-processor',
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler='handler.lambda_handler',
            code=lambda_.Code.from_asset('lambda/emotion_dynamics'),
            role=role,
            layers=[layer],
            memory_size=1024,
            timeout=Duration.seconds(15),
            ephemeral_storage=Size.mebibytes(1024),
            environment={
                'AWS_REGION': self.region,
                'VOICE_ID': 'Joanna',
                'LOG_LEVEL': 'INFO',
                'ENABLE_SSML': 'true',
                'ENABLE_VOLUME_DETECTION': 'true',
                'ENABLE_RATE_DETECTION': 'true',
                'ENABLE_METRICS': 'true',
                'MIN_STABILITY_THRESHOLD': '0.85',
                'MAX_RETRIES': '3',
                'AUDIO_SAMPLE_RATE': '16000',
                'STRUCTURED_LOGGING': 'true'
            },
            description='Emotion dynamics detection and SSML generation'
        )
```

## Performance Optimization

### Cold Start Optimization

**Strategies**:
1. Use Lambda layers to reduce deployment package size
2. Initialize heavy libraries outside handler
3. Use provisioned concurrency for critical paths
4. Cache librosa models in /tmp

**Example**:

```python
import librosa
import numpy as np
from emotion_dynamics.orchestrator import AudioDynamicsOrchestrator

# Initialize outside handler (reused across invocations)
orchestrator = AudioDynamicsOrchestrator()

def lambda_handler(event, context):
    """Lambda entry point."""
    # Handler uses pre-initialized orchestrator
    result = orchestrator.process_audio_and_text(
        audio_data=event['audio_data'],
        sample_rate=event['sample_rate'],
        translated_text=event['text']
    )
    return result
```

### Memory Optimization

**Monitor actual usage**:

```bash
# Check CloudWatch Logs for memory usage
aws logs filter-log-events \
    --log-group-name /aws/lambda/emotion-dynamics-processor \
    --filter-pattern "Max Memory Used" \
    --limit 100
```

**Adjust memory based on metrics**:
- If usage < 700 MB: Consider reducing to 768 MB
- If usage > 900 MB: Keep at 1024 MB
- Monitor for OOM errors

## Monitoring and Observability

### CloudWatch Metrics

**Custom Metrics**:
- `EmotionDynamics/VolumeDetectionLatency`
- `EmotionDynamics/RateDetectionLatency`
- `EmotionDynamics/SSMLGenerationLatency`
- `EmotionDynamics/PollySynthesisLatency`
- `EmotionDynamics/EndToEndLatency`
- `EmotionDynamics/ErrorCount`
- `EmotionDynamics/FallbackCount`

**Lambda Metrics**:
- Invocations
- Errors
- Throttles
- Duration
- Concurrent Executions

### CloudWatch Alarms

```python
# Latency alarm
latency_alarm = cloudwatch.Alarm(
    self,
    'EmotionDynamicsLatencyAlarm',
    metric=cloudwatch.Metric(
        namespace='EmotionDynamics',
        metric_name='EndToEndLatency',
        statistic='p95',
        period=Duration.minutes(5)
    ),
    threshold=1000,  # 1 second
    evaluation_periods=2,
    comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
)

# Error rate alarm
error_alarm = cloudwatch.Alarm(
    self,
    'EmotionDynamicsErrorAlarm',
    metric=cloudwatch.Metric(
        namespace='EmotionDynamics',
        metric_name='ErrorCount',
        statistic='Sum',
        period=Duration.minutes(5)
    ),
    threshold=10,
    evaluation_periods=2,
    comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
)
```

## Testing

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Test Lambda handler locally
python -c "
from handler import lambda_handler
event = {
    'audio_data': [...],
    'sample_rate': 16000,
    'text': 'Hello world'
}
result = lambda_handler(event, None)
print(result)
"
```

### Deployment Testing

```bash
# Deploy to dev environment
cdk deploy EmotionDynamicsStack --context env=dev

# Invoke Lambda function
aws lambda invoke \
    --function-name emotion-dynamics-processor \
    --payload file://test-event.json \
    --cli-binary-format raw-in-base64-out \
    response.json

# Check response
cat response.json
```

## Troubleshooting

### Common Issues

**Issue 1: Out of Memory (OOM)**
- **Symptom**: Lambda exits with "Task timed out" or memory error
- **Solution**: Increase memory to 1536 MB or optimize audio buffer size

**Issue 2: Timeout**
- **Symptom**: Lambda times out after 15 seconds
- **Solution**: Check Polly retry logic, reduce max retries, or increase timeout

**Issue 3: librosa Import Error**
- **Symptom**: "No module named 'librosa'" or "cannot import name"
- **Solution**: Ensure Lambda layer is attached or dependencies are in package

**Issue 4: Cold Start Latency**
- **Symptom**: First invocation takes >5 seconds
- **Solution**: Use provisioned concurrency or optimize initialization

**Issue 5: Polly Throttling**
- **Symptom**: "ThrottlingException" from Polly
- **Solution**: Implement exponential backoff (already in code) or request limit increase

## Cost Optimization

### Estimated Costs

**Per 1000 invocations** (3-second audio, 1-second execution):
- Lambda compute: $0.0000166667 × 1024 MB × 1s × 1000 = $0.017
- Lambda requests: $0.20 per 1M requests = $0.0002
- Polly synthesis: $0.004 per request × 1000 = $4.00
- CloudWatch Logs: ~$0.01
- **Total**: ~$4.03 per 1000 invocations

**Optimization strategies**:
1. Cache Polly results for repeated text (not applicable for real-time)
2. Use Lambda reserved concurrency to control costs
3. Monitor and optimize memory usage
4. Use CloudWatch Logs retention policies

## Security Considerations

### IAM Permissions

**Principle of Least Privilege**:
- Only grant `polly:SynthesizeSpeech` (not `polly:*`)
- Restrict CloudWatch metrics to specific namespace
- No S3 or DynamoDB access unless required

### Data Protection

**In Transit**:
- All AWS API calls use HTTPS/TLS 1.2+
- Audio data encrypted in transit

**At Rest**:
- No persistent storage of audio or text
- Temporary files in /tmp are ephemeral

### Secrets Management

**Never**:
- Hard-code credentials
- Log sensitive data (audio, text)
- Store API keys in environment variables

**Instead**:
- Use IAM roles for AWS service access
- Use Secrets Manager for third-party API keys (if needed)
- Sanitize logs to remove PII

## Deployment Checklist

- [ ] Dependencies installed and tested locally
- [ ] Unit tests passing (>80% coverage)
- [ ] Integration tests passing
- [ ] Lambda layer created (if using)
- [ ] IAM role created with correct permissions
- [ ] Environment variables configured
- [ ] CloudWatch alarms configured
- [ ] Deployment tested in dev environment
- [ ] Performance validated (<1s latency)
- [ ] Cost estimated and approved
- [ ] Security review completed
- [ ] Documentation updated

## References

- [AWS Lambda Python Runtime](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html)
- [AWS Lambda Layers](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html)
- [Amazon Polly SSML](https://docs.aws.amazon.com/polly/latest/dg/supportedtags.html)
- [librosa Documentation](https://librosa.org/doc/latest/index.html)
- [AWS CDK Python](https://docs.aws.amazon.com/cdk/api/v2/python/)
