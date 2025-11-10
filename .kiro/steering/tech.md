---
inclusion: always
---

# Technology Stack

## Primary Technologies

### Backend (Core Platform)

**Language**: Python 3.11+
- Type hints for all functions
- AsyncIO for concurrent operations
- boto3 for AWS SDK

**Compute**: AWS Lambda (Serverless)
- Session Management: 512MB, 10s timeout
- Audio Processing: 1024MB, 60s timeout
- Translation Pipeline: 1024MB, 30s timeout
- Authorizer: 128MB, 5s timeout

**API Gateway**: AWS API Gateway WebSocket API
- Manages persistent bidirectional connections
- Routes: $connect, $disconnect, custom routes
- 2-hour connection limit (solved with auto-refresh)
- 10-minute idle timeout

**Database**: Amazon DynamoDB
- On-demand capacity mode
- TTL-based auto-cleanup
- GSI for language-based queries
- Atomic counter operations

**Authentication**: Amazon Cognito User Pools
- JWT tokens for speakers
- RS256 algorithm
- 24-hour token expiration
- Anonymous listeners (no auth)

### Audio Processing

**Transcription**: AWS Transcribe Streaming API
- Partial results with stability scores
- 50+ source languages
- Real-time streaming

**Translation**: AWS Translate
- 75+ language pairs
- Caching in DynamoDB (1-hour TTL)
- Parallel processing

**Text-to-Speech**: AWS Polly
- Neural voices
- SSML support (prosody tags)
- MP3 output, 24kHz sample rate

**Audio Analysis**: librosa 0.10+
- RMS energy (volume detection)
- Onset detection (speaking rate)
- Feature extraction
- Lightweight processing (<100ms)

### Frontend

**Framework**: React 18+ with TypeScript
- Functional components with hooks
- Zustand for state management
- Web Audio API for audio processing

**Build Tool**: Vite
- Fast HMR (Hot Module Replacement)
- Code splitting
- Tree shaking
- Bundle target: <500KB

**UI Library**: Material-UI or custom components
- Accessibility-first (WCAG 2.1 Level AA)
- Responsive design
- Dark mode support

**WebSocket Client**: Native WebSocket API
- No external dependencies
- Custom reconnection logic
- Message queue management

**Authentication**: amazon-cognito-identity-js
- Cognito User Pool integration
- JWT token management
- Secure token storage

### Infrastructure as Code

**IaC Tool**: AWS CDK (Python)
- Type-safe infrastructure definitions
- Reusable constructs
- Multi-environment support

**CI/CD**: GitHub Actions or AWS CodePipeline
- Automated testing on PR
- Automated deployment to staging
- Manual approval for production

### Testing

**Backend Testing**:
- pytest for unit/integration tests
- moto for AWS service mocking
- Coverage target: >80%

**Frontend Testing**:
- Jest + React Testing Library (unit)
- Playwright or Cypress (E2E)
- Lighthouse (performance)

**Load Testing**:
- Custom scripts or Locust
- Target: 100 sessions, 500 listeners

### Monitoring & Observability

**Logs**: AWS CloudWatch Logs
- Structured JSON format
- 12-hour retention (configurable)
- Correlation IDs throughout

**Metrics**: AWS CloudWatch Metrics
- Custom metrics for business logic
- Standard metrics for AWS services
- Dashboard with key indicators

**Tracing**: AWS X-Ray (optional)
- Distributed tracing
- Performance analysis
- Bottleneck identification

**Frontend Monitoring**: AWS CloudWatch RUM
- Real user monitoring
- Performance metrics
- Error tracking

## Technology Constraints

### AWS Service Limits

- **API Gateway WebSocket**: 2-hour max connection duration
- **Lambda**: 15-minute max execution (not applicable for our use)
- **DynamoDB**: No practical limits with on-demand
- **Transcribe**: Real-time streaming, final results have variable latency
- **Translate**: 10K characters per request
- **Polly**: 3K characters per request

### Audio Processing Limits

- **Librosa**: CPU-intensive, ~100ms for 3s audio chunk
- **Lambda Memory**: 1024MB needed for librosa + numpy
- **Web Audio API**: Browser-dependent performance
- **Sample Rates**: 8kHz, 16kHz, 24kHz, 48kHz supported

### Network Constraints

- **Message Size**: 1MB max (API Gateway WebSocket)
- **Bandwidth**: 1 Mbps upload (speaker), 256 Kbps download (listener)
- **Latency**: Network RTT affects overall latency

## Technology Decisions & Rationale

### Why Serverless?

**Pros**:
- Zero idle cost (critical for cost targets)
- Auto-scaling
- No server management
- Pay per use

**Cons**:
- Cold starts (mitigated with provisioned concurrency if needed)
- 15-minute execution limit (not an issue for our use case)
- Vendor lock-in (acceptable for AWS-centric project)

**Decision**: Serverless is optimal for our use case

### Why DynamoDB?

**Pros**:
- Single-digit millisecond latency
- Auto-scaling with on-demand
- TTL for automatic cleanup
- GSI for flexible queries
- Atomic operations

**Cons**:
- NoSQL (requires careful data modeling)
- Cost can be high (on-demand helps)
- No joins (not needed for our access patterns)

**Decision**: Perfect fit for session state management

### Why Partial Results?

**Initial spec rejected partial results**. We pivoted because:

**Pros**:
- 50% latency reduction (4-7s → 2-4s)
- Better user experience
- Industry standard approach

**Cons**:
- 90% vs 98% accuracy
- More complex logic
- Requires deduplication

**Decision**: Trade-off worth it for latency improvement

### Why Audio Dynamics vs Text Sentiment?

**Initial approach**: Text sentiment analysis (Amazon Comprehend)

**Better approach**: Audio dynamics extraction (librosa)

**Rationale**:
- Preserves HOW speaker spoke (paralinguistic features)
- Text sentiment only captures WHAT was said
- Volume and rate map directly to SSML
- No external API calls (lower cost, latency)
- Comprehend doesn't help much with Polly SSML

### Why Christian/Bible Vocabulary?

**Session ID word lists** use Christian/Bible themes:
- Faithful, blessed, gracious, righteous
- Shepherd, covenant, temple, prophet

**Rationale**:
- Target audience: Religious organizations
- Memorable, positive words
- 100+ words available

**Alternative considered**: Nature/geography themes (if broader market)

## Dependencies & Versions

### Python Dependencies (Backend)

```
boto3>=1.28.0              # AWS SDK
botocore>=1.31.0           # AWS SDK core
librosa>=0.10.0            # Audio analysis
numpy>=1.24.0              # Numerical computing
soundfile>=0.12.0          # Audio I/O (librosa dependency)
PyJWT>=2.8.0               # JWT token validation
cryptography>=41.0.0       # JWT signatures
requests>=2.31.0           # HTTP client
pytest>=7.4.0              # Testing
pytest-asyncio>=0.21.0     # Async testing
moto>=4.2.0                # AWS mocking
```

### TypeScript Dependencies (Frontend)

```
react@^18.2.0                          # UI framework
react-dom@^18.2.0                      # React DOM
typescript@^5.0.0                      # Type safety
vite@^4.4.0                            # Build tool
zustand@^4.4.0                         # State management
amazon-cognito-identity-js@^6.3.0      # Cognito auth
@mui/material@^5.14.0                  # UI components (optional)
@types/react@^18.2.0                   # React types
@types/react-dom@^18.2.0               # React DOM types
jest@^29.6.0                           # Testing
@testing-library/react@^14.0.0         # React testing
playwright@^1.38.0                     # E2E testing
```

### AWS CDK Dependencies

```
aws-cdk-lib>=2.100.0       # CDK core
constructs>=10.0.0         # CDK constructs
```

## Development Tools

### Code Quality

- **Linting**: pylint, flake8 (Python), ESLint (TypeScript)
- **Formatting**: black (Python), Prettier (TypeScript)
- **Type Checking**: mypy (Python), tsc (TypeScript)
- **Security Scanning**: bandit (Python), npm audit (TypeScript)

### Local Development

- **Python**: pyenv for version management
- **Node**: nvm for version management
- **AWS**: AWS CLI v2, AWS SAM CLI (optional)
- **Docker**: For local DynamoDB (optional)

### Documentation

- **API Docs**: Swagger/OpenAPI for REST APIs
- **Code Docs**: Docstrings (Python), JSDoc (TypeScript)
- **Architecture**: Mermaid diagrams in markdown
- **Runbooks**: Markdown in docs/ directory

## Security Technologies

### Data Protection

- **In Transit**: TLS 1.2+ (WSS, HTTPS)
- **At Rest**: DynamoDB encryption (AWS-managed keys)
- **Tokens**: Encrypted localStorage (crypto-js)

### Access Control

- **IAM**: Least privilege roles
- **Cognito**: User authentication
- **API Gateway**: Lambda authorizers

### Compliance

- **GDPR**: No persistent audio/transcript storage
- **Logging**: PII sanitization
- **Audit**: CloudTrail for API calls

## Performance Targets

### Latency Targets

| Operation | Target | Maximum |
|-----------|--------|---------|
| Session creation | 2s | 3s |
| Listener join | 1s | 2s |
| End-to-end audio | 2-4s | 5s |
| Control response | 100ms | 200ms |
| Language switch | 500ms | 1s |

### Scalability Targets

- **Concurrent Sessions**: 100
- **Listeners per Session**: 500
- **Traffic Spikes**: 10x normal load
- **Geographic Distribution**: Single region (v1.0), multi-region (v2.0)

### Cost Targets

- **Per listener-hour**: <$0.10 (actual: ~$0.04)
- **Monthly** (100 sessions/day): ~$170
- **Breakdown**:
  - API Gateway: $30
  - Lambda: $40
  - DynamoDB: $25
  - Transcribe: $35
  - Translate: $15 (with caching)
  - Polly: $10
  - CloudWatch: $10
  - S3/CloudFront: $5

## Technology Risk Assessment

### High Risk

- **Librosa Performance**: May exceed 5% overhead budget
  - Mitigation: Benchmark early, optimize or increase memory

- **WebSocket Stability**: Connection drops affect UX
  - Mitigation: Robust reconnection, connection refresh

### Medium Risk

- **Translation Costs**: Cache hit rate may be lower than 50%
  - Mitigation: Monitor metrics, adjust cache TTL

- **End-to-End Latency**: May exceed 4s target
  - Mitigation: Measure each stage, optimize bottlenecks

### Low Risk

- **AWS Service Availability**: 99.99% SLA
- **DynamoDB Performance**: Proven at scale
- **Lambda Scaling**: Automatic, reliable

## Technology Evolution

### Immediate (v1.0)

Current stack as specified

### Near-term (v1.1-2.0)

- **Edge Computing**: CloudFront Lambda@Edge for lower latency
- **Database**: ElastiCache Redis for hot data caching
- **Premium Mode**: SageMaker for emotion transfer model

### Long-term (v3.0+)

- **Audio Transport**: Consider WebRTC instead of WebSocket
- **Multi-region**: DynamoDB Global Tables
- **ML Platform**: SageMaker for custom models
- **Container**: ECS/EKS if Lambda limits become issue
