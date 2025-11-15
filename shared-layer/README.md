# Shared Lambda Layer

This directory contains shared utilities that are deployed as a Lambda Layer and attached to all Lambda functions in the WebSocket Audio Integration system.

## Contents

The shared layer includes:

- `structured_logger.py` - Structured logging utility
- `metrics_emitter.py` - CloudWatch metrics emitter
- `validators.py` - Input validation functions
- `error_codes.py` - Standardized error codes
- `table_names.py` - DynamoDB table name constants
- `websocket_messages.py` - WebSocket message schemas

## Structure

```
shared-layer/
├── python/
│   └── shared_utils/
│       ├── __init__.py
│       ├── structured_logger.py
│       ├── metrics_emitter.py
│       ├── validators.py
│       ├── error_codes.py
│       ├── table_names.py
│       └── websocket_messages.py
├── requirements.txt
├── build.sh
└── README.md
```

## Building the Layer

```bash
cd shared-layer
./build.sh
```

This creates `shared-layer.zip` ready for deployment.

## Deploying the Layer

The layer is deployed via CDK in the infrastructure stack:

```python
shared_layer = lambda_.LayerVersion(
    self, 'SharedUtilsLayer',
    code=lambda_.Code.from_asset('shared-layer/shared-layer.zip'),
    compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
    description='Shared utilities for WebSocket Audio Integration'
)
```

## Using the Layer

Once attached to a Lambda function, import utilities:

```python
from shared_utils import (
    get_structured_logger,
    ErrorCode,
    format_error_response,
    get_table_name,
    SESSIONS_TABLE_NAME
)

logger = get_structured_logger('MyFunction')
logger.info('Function started')
```

## Updating the Layer

1. Modify files in `python/shared_utils/`
2. Run `./build.sh` to rebuild
3. Deploy via CDK: `cdk deploy`
4. Lambda functions automatically use new version

## Version Management

- Layer versions are immutable
- Each deployment creates a new version
- Lambda functions reference latest version
- Old versions retained for rollback

## Dependencies

The layer includes these Python packages:
- boto3 (AWS SDK)
- None (utilities are self-contained)

## Size Limits

- Maximum layer size: 50MB (unzipped)
- Current size: ~100KB
- Well within limits

## Testing

Test layer utilities locally:

```bash
cd shared-layer
python -m pytest tests/
```

## Troubleshooting

**Import errors after deployment:**
- Verify layer attached to function in CDK
- Check layer path matches import statements
- Ensure layer compatible with Python 3.11

**Layer too large:**
- Remove unnecessary dependencies
- Use separate layers for large packages

## Related Documentation

- [AWS Lambda Layers](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html)
- [CDK Lambda Layer](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/LayerVersion.html)
