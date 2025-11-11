# Audio Transcription - Deployment Guide

Comprehensive guide for deploying the audio-transcription component.

## Current Status

⚠️ **Note**: This component is in active development (Tasks 1-3 complete). Full deployment procedures will be available after Lambda functions and infrastructure are implemented (Tasks 10-12).

## Prerequisites

### Required Tools
- Python 3.11+
- AWS CLI v2
- AWS CDK CLI (will be added in Task 12)
- Git
- Make

### AWS Requirements
- AWS account with appropriate permissions
- IAM role for Lambda execution
- Access to:
  - AWS Transcribe
  - AWS Translate
  - AWS Polly
  - DynamoDB
  - CloudWatch

### Credentials Setup

```bash
# Configure AWS CLI
aws configure

# Verify credentials
aws sts get-caller-identity
```

## Development Environment

### Local Setup

```bash
# Clone repository
git clone https://github.com/your-org/low-latency-translate.git
cd low-latency-translate/audio-transcription

# Install dependencies
make install

# Run tests
make test

# Verify installation
python -c "from shared.models import PartialResult; print('✓ OK')"
```

### Environment Variables

Create `.env` file for local development:

```bash
# Partial Results Configuration
PARTIAL_RESULTS_ENABLED=true
MIN_STABILITY_THRESHOLD=0.85
MAX_BUFFER_TIMEOUT=5.0
PAUSE_THRESHOLD=2.0
ORPHAN_TIMEOUT=15.0
MAX_RATE_PER_SECOND=5
DEDUP_CACHE_TTL=10

# AWS Configuration (for local testing)
AWS_REGION=us-east-1
AWS_PROFILE=default
```

## Testing Before Deployment

### Unit Tests

```bash
# Run all unit tests
make test

# Run with coverage report
pytest --cov=shared --cov-report=html

# View coverage report
open htmlcov/index.html
```

**Requirements**:
- All tests must pass
- Coverage must be ≥80%
- No linting errors

### Code Quality

```bash
# Format code
make format

# Run linters
make lint

# Type checking
mypy shared/
```

## Deployment Environments

### Environment Overview

| Environment | Purpose | Auto-Deploy | Approval Required |
|-------------|---------|-------------|-------------------|
| **dev** | Development testing | Yes | No |
| **staging** | Pre-production validation | Yes | No |
| **prod** | Production | No | Yes (manual) |

### Environment Configuration

Each environment has specific configuration:

**Dev**:
- Partial results: Enabled
- Stability threshold: 0.80 (lower for testing)
- Buffer timeout: 7.0 seconds (longer for debugging)
- Rate limit: 10/second (higher for testing)

**Staging**:
- Partial results: Enabled
- Stability threshold: 0.85 (production-like)
- Buffer timeout: 5.0 seconds
- Rate limit: 5/second

**Production**:
- Partial results: Enabled (with feature flag)
- Stability threshold: 0.85
- Buffer timeout: 5.0 seconds
- Rate limit: 5/second

## Deployment Procedures

### Pre-Deployment Checklist

- [ ] All tests passing locally
- [ ] Code coverage ≥80%
- [ ] No linting errors
- [ ] Documentation updated
- [ ] Task summary created
- [ ] Code reviewed and approved
- [ ] Changes committed to main branch

### Deploy to Dev

⚠️ **Coming Soon**: Deployment commands will be available after infrastructure is implemented (Task 12).

```bash
# Will be available after Task 12
make deploy-dev
```

### Deploy to Staging

```bash
# Will be available after Task 12
make deploy-staging
```

### Deploy to Production

```bash
# Will be available after Task 12
# Requires manual approval
make deploy-prod
```

## Post-Deployment Verification

### Smoke Tests

After deployment, verify basic functionality:

```bash
# Will be available after Lambda integration (Task 12)
# Test partial result processing
# Test deduplication
# Test buffer operations
```

### Monitoring

Check CloudWatch metrics:

- `PartialResultProcessingLatency` - Should be <100ms
- `PartialResultsDropped` - Should be <10/minute
- `OrphanedResultsFlushed` - Should be <5/session
- `DuplicatesDetected` - Should be <5/session

### Health Checks

```bash
# Will be available after Lambda integration
# Check Lambda function health
# Check DynamoDB table status
# Check CloudWatch logs
```

## Rollback Procedures

### Quick Rollback

If issues are detected after deployment:

```bash
# Will be available after infrastructure (Task 12)
# Rollback to previous version
make rollback
```

### Feature Flag Rollback

Disable partial results without redeployment:

```bash
# Update Lambda environment variable
aws lambda update-function-configuration \
  --function-name audio-processor \
  --environment Variables={PARTIAL_RESULTS_ENABLED=false}
```

### Manual Rollback

1. Identify last known good version
2. Deploy that version to affected environment
3. Verify functionality
4. Monitor metrics

## Monitoring and Alerting

### CloudWatch Dashboards

**Will be configured in Task 13**:
- Partial result processing latency
- Rate limiting metrics
- Buffer capacity metrics
- Cache hit rates
- Error rates

### Alarms

**Critical Alarms** (page on-call):
- End-to-end latency p95 > 5 seconds
- Error rate > 5%
- Lambda function errors

**Warning Alarms** (email):
- Partial results dropped > 100/minute
- Orphaned results > 10/session
- Cache size > 5000 entries

## Troubleshooting

### Common Issues

**Issue**: High latency after deployment

**Solution**:
1. Check CloudWatch metrics for bottlenecks
2. Verify stability threshold configuration
3. Check rate limiter settings
4. Review buffer capacity

**Issue**: High rate of dropped results

**Solution**:
1. Check rate limiter configuration
2. Verify AWS Transcribe is sending expected rate
3. Consider increasing rate limit for specific use case

**Issue**: Memory issues in Lambda

**Solution**:
1. Check buffer capacity settings
2. Verify cache cleanup is working
3. Increase Lambda memory allocation
4. Check for memory leaks in logs

### Logs

View Lambda logs:

```bash
# Will be available after Lambda integration
aws logs tail /aws/lambda/audio-processor --follow
```

Search for errors:

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/audio-processor \
  --filter-pattern "ERROR"
```

## Configuration Management

### Environment Variables

Update Lambda configuration:

```bash
aws lambda update-function-configuration \
  --function-name audio-processor \
  --environment Variables='{
    "PARTIAL_RESULTS_ENABLED":"true",
    "MIN_STABILITY_THRESHOLD":"0.85",
    "MAX_BUFFER_TIMEOUT":"5.0"
  }'
```

### Feature Flags

Use AWS AppConfig or Parameter Store for dynamic configuration:

```bash
# Will be implemented in Task 16
aws ssm put-parameter \
  --name /audio-transcription/partial-results-enabled \
  --value "true" \
  --type String
```

## Security

### IAM Permissions

Lambda execution role requires:
- `transcribe:StartStreamTranscription`
- `translate:TranslateText`
- `polly:SynthesizeSpeech`
- `dynamodb:GetItem`, `PutItem`, `UpdateItem`
- `logs:CreateLogGroup`, `CreateLogStream`, `PutLogEvents`
- `cloudwatch:PutMetricData`

### Secrets Management

No secrets required for this component. AWS service access is via IAM roles.

### Network Security

- Lambda functions run in VPC (optional)
- DynamoDB accessed via VPC endpoint (optional)
- All AWS service calls use TLS 1.2+

## Cost Management

### Estimated Costs

**Per 1000 sessions** (30 minutes each, 50 listeners):
- Lambda execution: ~$5
- DynamoDB: ~$3
- CloudWatch: ~$2
- **Total**: ~$10

### Cost Optimization

- Use on-demand DynamoDB (no idle cost)
- Right-size Lambda memory (512 MB recommended)
- Enable translation caching (50% cost reduction)
- Monitor and adjust rate limits

## Maintenance

### Regular Tasks

**Weekly**:
- Review CloudWatch metrics
- Check error rates
- Verify test coverage

**Monthly**:
- Update dependencies
- Review and optimize costs
- Update documentation

**Quarterly**:
- Security review
- Performance optimization
- Capacity planning

## Support

### Getting Help

- **Documentation**: Check `README.md` and `docs/` folder
- **Specifications**: See `.kiro/specs/realtime-audio-transcription/`
- **Team**: Contact Developer 3 (Translation & Integration Engineer)
- **On-Call**: Page via PagerDuty (production issues only)

### Escalation

1. Check documentation and logs
2. Review recent deployments
3. Check CloudWatch metrics
4. Contact team lead
5. Page on-call (critical issues only)

## Future Enhancements

### Planned Improvements

**Phase 1** (Tasks 4-12):
- Lambda function implementation
- AWS Transcribe integration
- CloudWatch metrics
- Infrastructure as Code (CDK)

**Phase 2** (Tasks 13-17):
- Enhanced monitoring
- Performance optimization
- Multi-region support
- Advanced caching strategies

## Appendix

### Useful Commands

```bash
# Check Lambda function status
aws lambda get-function --function-name audio-processor

# View recent logs
aws logs tail /aws/lambda/audio-processor --since 1h

# Check DynamoDB table
aws dynamodb describe-table --table-name CachedTranslations

# List CloudWatch alarms
aws cloudwatch describe-alarms --alarm-name-prefix audio-transcription
```

### Related Documentation

- [README.md](README.md) - Technical architecture
- [OVERVIEW.md](OVERVIEW.md) - Current status
- [QUICKSTART.md](QUICKSTART.md) - Local development setup
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - File organization
- [Implementation Roadmap](../implementation-roadmap.md) - Overall project plan
