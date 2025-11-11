---
inclusion: always
---

# Project Structure & Conventions

## High-Level Organization

```
low-latency-translate/
├── .kiro/                          # Kiro-specific files
│   ├── specs/                      # Technical specifications
│   └── steering/                   # Team steering docs (this dir)
│
├── session-management/             # Component 1: WebSocket & Sessions
├── audio-transcription/            # Component 2: Real-time transcription
├── translation-pipeline/           # Component 3: Translation & broadcasting
├── audio-quality/                  # Component 4: Quality validation
├── emotion-dynamics/               # Component 5: Dynamics & SSML
├── frontend-apps/                  # Component 6: Web applications
│
├── infrastructure/                 # Shared infrastructure (CDK)
├── docs/                          # Project documentation
├── scripts/                       # Deployment & utility scripts
│
├── implementation-roadmap.md      # 12-week execution plan
└── README.md                      # Project overview
```

## Component Structure Pattern

Each component follows this standard structure:

```
{component-name}/
├── lambda/                        # Lambda function handlers
│   ├── {function-name}/
│   │   ├── handler.py            # Lambda entry point
│   │   ├── requirements.txt      # Function-specific dependencies
│   │   └── __init__.py
│   └── layers/                   # Lambda layers (optional)
│
├── shared/                       # Shared code within component
│   ├── models/                   # Data models & types
│   │   ├── session.py           # Domain models
│   │   └── __init__.py
│   ├── data_access/             # Repository pattern
│   │   ├── dynamodb_client.py   # Base client
│   │   ├── {entity}_repository.py
│   │   ├── exceptions.py        # Custom exceptions
│   │   └── __init__.py
│   ├── services/                # Business logic
│   │   ├── {service}_service.py
│   │   └── __init__.py
│   ├── utils/                   # Utilities
│   │   ├── validators.py
│   │   ├── constants.py
│   │   └── __init__.py
│   └── config/                  # Configuration
│       ├── settings.py
│       └── __init__.py
│
├── infrastructure/              # Component-specific IaC
│   ├── stacks/
│   │   └── {component}_stack.py
│   ├── app.py                  # CDK app entry
│   └── cdk.json               # CDK config
│
├── tests/                      # All tests for component
│   ├── unit/                  # Unit tests
│   │   ├── test_{module}.py
│   │   └── __init__.py
│   ├── integration/           # Integration tests
│   │   ├── test_{feature}.py
│   │   └── __init__.py
│   ├── fixtures/              # Test fixtures
│   │   ├── {fixture}.py
│   │   └── __init__.py
│   └── conftest.py           # Pytest configuration
│
├── docs/                      # Component documentation
│   ├── TASK_1_SUMMARY.md    # Task 1 implementation summary
│   ├── TASK_2_SUMMARY.md    # Task 2 implementation summary
│   ├── ...                  # Additional task summaries
│   ├── TASK_N_SUMMARY.md    # Task N implementation summary
│   ├── RATE_LIMITING.md     # Feature-specific documentation (example)
│   └── {FEATURE}.md         # Other feature documentation as needed
│
├── requirements.txt           # Python dependencies
├── requirements-dev.txt      # Dev dependencies
├── Makefile                  # Common commands
├── pytest.ini                # Pytest config
├── setup.py                  # Package configuration
├── validate_structure.py     # Project structure validation
│
├── README.md                 # Component README (architecture, development)
├── OVERVIEW.md               # High-level overview (what, why, status)
├── QUICKSTART.md             # Quick start tutorial (5-minute setup)
├── PROJECT_STRUCTURE.md      # Detailed file structure documentation
├── DEPLOYMENT.md             # Deployment guide (detailed)
├── DEPLOYMENT_CHECKLIST.md   # Deployment checklist
└── DEPLOYMENT_QUICK_REFERENCE.md  # Quick deployment commands
```

## Documentation Structure Pattern

Each component MUST follow this documentation organization:

### Root-Level Documentation Files

These files live at the component root and serve different audiences:

**README.md** - Primary technical documentation
- Target: Developers and architects
- Content: Architecture overview, component design, development guide
- Includes: System diagrams, API contracts, integration points
- Length: Comprehensive (typically 500-1000 lines)

**OVERVIEW.md** - Executive summary and navigation
- Target: Project managers, new team members, stakeholders
- Content: What the component does, key features, current status
- Includes: Documentation guide (where to find what), quick commands
- Length: Concise (typically 200-400 lines)

**QUICKSTART.md** - Hands-on tutorial
- Target: Developers getting started
- Content: Step-by-step setup and deployment tutorial
- Includes: Prerequisites, installation, first deployment, verification
- Length: Tutorial-focused (typically 300-500 lines)

**PROJECT_STRUCTURE.md** - File organization reference
- Target: Developers navigating the codebase
- Content: Complete file tree with descriptions
- Includes: File counts, statistics, purpose of each directory
- Length: Detailed reference (typically 400-600 lines)

**DEPLOYMENT.md** - Comprehensive deployment guide
- Target: DevOps, deployment engineers
- Content: Detailed deployment procedures, configuration, troubleshooting
- Includes: Prerequisites, step-by-step instructions, rollback procedures
- Length: Comprehensive (typically 600-1000 lines)

**DEPLOYMENT_CHECKLIST.md** - Deployment verification checklist
- Target: DevOps performing deployments
- Content: Step-by-step checklist format
- Includes: Pre-deployment, deployment, post-deployment, rollback steps
- Length: Checklist format (typically 200-300 lines)

**DEPLOYMENT_QUICK_REFERENCE.md** - Command reference
- Target: Experienced operators needing quick command lookup
- Content: Organized command reference by category
- Includes: All deployment, testing, monitoring commands
- Length: Reference format (typically 200-400 lines)

### `/docs` Folder - Implementation Documentation

This folder contains task summaries and feature-specific documentation:

**TASK_N_SUMMARY.md** - Task implementation summaries
- One file per task (TASK_1_SUMMARY.md, TASK_2_SUMMARY.md, etc.)
- Content: Task description, requirements, tests, solution
- Purpose: Track what was implemented and how
- Created: After completing each task

**{FEATURE}.md** - Feature-specific documentation
- Examples: RATE_LIMITING.md, AUTHENTICATION.md, MONITORING.md
- Content: Deep dive into specific features
- Purpose: Detailed technical documentation for complex features
- Created: When a feature needs extensive documentation beyond code comments

### Documentation Hierarchy

```
Component Root
├── README.md                    # Start here for technical details
├── OVERVIEW.md                  # Start here for high-level understanding
├── QUICKSTART.md                # Start here to get running quickly
├── PROJECT_STRUCTURE.md         # Reference for file organization
├── DEPLOYMENT.md                # Comprehensive deployment guide
├── DEPLOYMENT_CHECKLIST.md      # Deployment verification steps
├── DEPLOYMENT_QUICK_REFERENCE.md # Quick command reference
│
└── docs/                        # Implementation details
    ├── TASK_*_SUMMARY.md        # What was built and how
    └── {FEATURE}.md             # Feature deep dives
```

### Documentation Cross-References

Documents should reference each other appropriately:

- **OVERVIEW.md** → Links to all other docs with audience-specific guidance
- **README.md** → Links to QUICKSTART.md, DEPLOYMENT.md, specs
- **QUICKSTART.md** → Links to README.md for details, DEPLOYMENT.md for production
- **PROJECT_STRUCTURE.md** → Links to task summaries for implementation details
- **DEPLOYMENT.md** → Links to DEPLOYMENT_CHECKLIST.md and DEPLOYMENT_QUICK_REFERENCE.md

### Documentation Maintenance

- Update **README.md** when architecture or APIs change
- Update **OVERVIEW.md** when status or features change
- Update **PROJECT_STRUCTURE.md** when files are added/removed/moved
- Update **validate_structure.py** when required files change
- Create new **TASK_N_SUMMARY.md** after completing each task
- Update **DEPLOYMENT.md** when deployment procedures change

## File Naming Conventions

### Python Files

**Modules**: `snake_case.py`
- Example: `session_id_generator.py`, `dynamodb_client.py`

**Classes**: `PascalCase`
- Example: `SessionIdGenerator`, `DynamoDBClient`

**Functions & Variables**: `snake_case`
- Example: `generate_session_id()`, `listener_count`

**Constants**: `UPPER_SNAKE_CASE`
- Example: `MAX_LISTENERS_PER_SESSION`, `SESSION_MAX_DURATION_HOURS`

**Private**: Prefix with underscore
- Example: `_validate_input()`, `_internal_method()`

### TypeScript/React Files

**Components**: `PascalCase.tsx`
- Example: `SessionCreator.tsx`, `AudioVisualizer.tsx`

**Utilities**: `camelCase.ts`
- Example: `audioProcessor.ts`, `webSocketClient.ts`

**Types/Interfaces**: `PascalCase` in `types.ts` or `interfaces.ts`
- Example: `interface AudioState`, `type SessionId`

**Hooks**: `use` + `PascalCase.ts`
- Example: `useWebSocket.ts`, `useAudioCapture.ts`

**Constants**: `UPPER_SNAKE_CASE` in `constants.ts`

### Test Files

**Pattern**: `test_{module_name}.py` or `{ComponentName}.test.tsx`
- Example: `test_session_repository.py`, `AudioVisualizer.test.tsx`

**Test Classes**: `Test{FeatureName}`
- Example: `TestAtomicCounterOperations`, `TestSessionIdGeneration`

**Test Methods**: `test_{scenario}`
- Example: `test_atomic_increment_listener_count()`

## Import Patterns

### Python

**Standard Library** → **Third-Party** → **Local**

```python
# Standard library
import time
import logging
from typing import Dict, List, Optional

# Third-party
import boto3
from botocore.exceptions import ClientError

# Local (absolute imports from component root)
from shared.models.session import Session
from shared.data_access.dynamodb_client import DynamoDBClient
from shared.utils.validators import validate_session_id
```

**Avoid**:
- Relative imports across packages
- Star imports (`from module import *`)
- Circular dependencies

### TypeScript/React

**React** → **Third-Party** → **Local**

```typescript
// React
import React, { useState, useEffect } from 'react';

// Third-party
import { Button, TextField } from '@mui/material';

// Local types
import type { AudioState, SessionId } from '../types';

// Local components
import { ConnectionStatus } from './ConnectionStatus';

// Local utilities
import { webSocketClient } from '../services/webSocketClient';
```

**Use aliases** for cleaner imports:
```typescript
import { AudioState } from '@/types';
import { useWebSocket } from '@/hooks';
```

## Directory Layout Standards

### Lambda Functions

```
lambda/{function-name}/
├── handler.py              # Entry point: lambda_handler()
├── requirements.txt        # Function-specific deps
├── README.md              # Function purpose & usage
└── __init__.py
```

**Entry Point Pattern**:
```python
def lambda_handler(event, context):
    """
    Lambda entry point.
    
    Args:
        event: Lambda event object
        context: Lambda context object
        
    Returns:
        Response dict with statusCode and body
    """
    pass
```

### Shared Libraries

**Models** (`shared/models/`):
- Dataclasses or Pydantic models
- Immutable where possible
- Validation in `__post_init__`

**Repositories** (`shared/data_access/`):
- One repository per DynamoDB table
- Encapsulates all DB operations
- Uses DynamoDBClient for atomic operations

**Services** (`shared/services/`):
- Business logic layer
- Coordinates between repositories
- Handles transactions

**Utils** (`shared/utils/`):
- Pure functions (no side effects)
- Reusable across component
- Well-tested

### Tests

**Structure mirrors source**:
```
shared/services/session_service.py
  → tests/unit/test_session_service.py

lambda/authorizer/handler.py
  → tests/integration/test_authorizer_integration.py
```

**Fixtures** in `tests/fixtures/`:
- Reusable test data
- Mock objects
- Test helpers

## Architecture Patterns

### Repository Pattern

**Purpose**: Abstract data access

```python
class SessionsRepository:
    """Repository for Session entities."""
    
    def __init__(self, table_name: str, client: DynamoDBClient):
        self.table_name = table_name
        self.client = client
    
    def create_session(self, session_id, ...):
        """Create new session."""
        pass
    
    def get_session(self, session_id):
        """Get session by ID."""
        pass
```

**Benefits**:
- Testable (mock DynamoDBClient)
- Reusable
- Single responsibility

### Service Layer Pattern

**Purpose**: Business logic coordination

```python
class SessionService:
    """Service for session management business logic."""
    
    def __init__(self, sessions_repo, connections_repo):
        self.sessions_repo = sessions_repo
        self.connections_repo = connections_repo
    
    def create_speaker_session(self, user_id, ...):
        """Coordinate session creation with validation."""
        # Validate inputs
        # Generate session ID
        # Create session record
        # Return session details
        pass
```

**Benefits**:
- Separates business logic from data access
- Orchestrates multiple repositories
- Testable with repository mocks

### Event-Driven Pattern

**Lambda handlers** are event-driven:

```python
def lambda_handler(event, context):
    # Parse event
    event_type = event['requestContext']['eventType']
    
    # Route to handler
    if event_type == 'CONNECT':
        return handle_connect(event)
    elif event_type == 'DISCONNECT':
        return handle_disconnect(event)
```

**WebSocket events**:
- $connect → Connection Handler
- $disconnect → Disconnect Handler
- sendAudio → Audio Processor
- heartbeat → Heartbeat Handler

## Configuration Management

### Environment-Specific

**Environments**: dev, staging, prod

**Configuration Files**:
```
config/
├── dev.env              # Development
├── staging.env          # Staging
└── prod.env            # Production
```

**Loading**:
```python
import os

# Lambda gets from environment variables
TABLE_NAME = os.environ['SESSIONS_TABLE_NAME']
REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Frontend gets from build-time injection
const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT;
```

### Feature Flags

**Use environment variables**:
```python
PARTIAL_RESULTS_ENABLED = os.getenv('PARTIAL_RESULTS_ENABLED', 'true') == 'true'
ENABLE_SSML = os.getenv('ENABLE_SSML', 'true') == 'true'
```

**Benefits**:
- Runtime toggle without redeployment
- Gradual rollout
- Emergency rollback

## Documentation Standards

### Code Documentation

**Python** (PEP 257):
```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description on first line.
    
    Detailed description if needed. Explain complex logic,
    edge cases, or important behavior.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When param1 is invalid
        DynamoDBError: When database operation fails
    """
    pass
```

**TypeScript** (JSDoc):
```typescript
/**
 * Brief description on first line.
 * 
 * Detailed description if needed.
 * 
 * @param param1 - Description
 * @param param2 - Description
 * @returns Description of return
 * @throws {Error} When something goes wrong
 */
function functionName(param1: string, param2: number): boolean {
  // Implementation
}
```

### Component READMEs

**Required sections**:
1. Overview (what it does)
2. Architecture (how it works)
3. Setup (how to run locally)
4. Testing (how to test)
5. Deployment (how to deploy)
6. Troubleshooting (common issues)

**Example**: See `session-management/README.md`

### API Documentation

**WebSocket Messages**: Document in `docs/API.md`
- Message type
- Direction (client→server or server→client)
- Parameters
- Example JSON
- Error responses

## Version Control Standards

### Branch Naming

- `main` - Production-ready code
- `develop` - Integration branch (if using git-flow)
- `feature/{component}-{description}` - Feature branches
- `fix/{component}-{description}` - Bug fixes
- `hotfix/{description}` - Production hotfixes

**Examples**:
- `feature/session-management-connection-refresh`
- `fix/transcription-stability-threshold`
- `hotfix/rate-limit-bypass`

### Commit Messages

**Format**: `{type}({scope}): {description}`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Tests
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `chore`: Maintenance

**Examples**:
```
feat(session-mgmt): implement connection refresh handler
fix(transcription): handle missing stability scores
docs(steering): add team coding standards
test(data-access): add atomic counter tests
```

### PR Guidelines

**Required**:
- Link to specification requirement
- Description of changes
- Testing performed
- Screenshots (if UI changes)

**Template**:
```markdown
## Requirements
Addresses: [Requirement X, Criterion Y]

## Changes
- Implemented feature A
- Fixed bug B
- Updated documentation

## Testing
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Manual testing completed

## Screenshots
[If applicable]
```

## Build & Deployment Structure

### Makefile Commands

**Standard commands** for all components:

```makefile
install:        # Install dependencies
test:           # Run tests
lint:           # Run linters
format:         # Format code
build:          # Build artifacts
deploy-dev:     # Deploy to dev
deploy-staging: # Deploy to staging
deploy-prod:    # Deploy to production
clean:          # Clean build artifacts
```

**Usage**:
```bash
make install
make test
make deploy-dev
```

### Infrastructure as Code

**CDK Stack Organization**:
```python
# infrastructure/stacks/{component}_stack.py

class SessionManagementStack(Stack):
    """
    CDK stack for Session Management component.
    Includes: DynamoDB tables, Lambda functions, IAM roles.
    """
    
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # DynamoDB Tables
        self._create_sessions_table()
        self._create_connections_table()
        
        # Lambda Functions
        self._create_authorizer()
        self._create_connection_handler()
```

**Environment-specific**: Use CDK context for configuration

### Deployment Pipeline

**Stages**:
1. **Build**: Install deps, run tests, create artifacts
2. **Test**: Run integration tests against staging
3. **Deploy**: Deploy via CDK
4. **Smoke Test**: Basic functionality validation
5. **Monitor**: Check metrics for 30 minutes

**Automation**: Triggered on PR merge to main

## Logging Standards

### Structured Logging Format

```python
import json
import logging

logger = logging.getLogger(__name__)

# Structured log entry
logger.info(json.dumps({
    "timestamp": "2025-11-10T12:34:56.789Z",
    "level": "INFO",
    "correlation_id": "session-123-conn-456",
    "component": "SessionService",
    "operation": "create_session",
    "message": "Session created successfully",
    "session_id": "golden-eagle-427",
    "duration_ms": 145
}))
```

### Log Levels

- **DEBUG**: Detailed diagnostic (partial results, buffer operations)
- **INFO**: Normal operations (session created, listener joined)
- **WARNING**: Unexpected but handled (rate limit hit, cache miss)
- **ERROR**: Errors requiring attention (service failure, invalid state)

### Correlation IDs

**Format**: `{session_id}` or `{session_id}-{connection_id}`

**Usage**: Include in all log entries for request tracing

## Error Handling Standards

### Exception Hierarchy

```python
# Base exception
class ApplicationError(Exception):
    """Base exception for application errors."""
    pass

# Specific exceptions
class DynamoDBError(ApplicationError):
    """DynamoDB operation error."""
    pass

class ValidationError(ApplicationError):
    """Input validation error."""
    pass

class ConditionalCheckFailedError(DynamoDBError):
    """DynamoDB conditional check failed."""
    pass
```

### Error Response Format

**Lambda/API responses**:
```json
{
  "statusCode": 400,
  "body": {
    "type": "error",
    "code": "INVALID_SESSION_ID",
    "message": "Session ID format invalid",
    "details": {
      "field": "sessionId",
      "provided": "invalid-123"
    },
    "timestamp": 1699500000000
  }
}
```

### Error Handling Pattern

```python
try:
    # Operation
    result = perform_operation()
except RetryableError as e:
    # Retry with backoff
    result = retry_with_backoff(perform_operation)
except ValidationError as e:
    # User error - return 400
    return error_response(400, str(e))
except ApplicationError as e:
    # Application error - log and return 500
    logger.error(f"Application error: {e}", exc_info=True)
    return error_response(500, "Internal error")
```

## Testing Organization

### Test File Structure

**Mirrors source structure**:
```
shared/services/session_service.py
  → tests/unit/test_session_service.py
  → tests/integration/test_session_integration.py
```

### Test Class Organization

```python
class TestFeatureName:
    """Test suite for Feature."""
    
    @pytest.fixture
    def mock_dependency(self):
        """Fixture for mock."""
        return Mock()
    
    def test_success_scenario(self):
        """Test successful operation."""
        pass
    
    def test_error_scenario(self):
        """Test error handling."""
        pass
    
    def test_edge_case(self):
        """Test edge case."""
        pass
```

### Test Naming

**Pattern**: `test_{scenario}_{expected_result}`

**Examples**:
- `test_create_session_with_valid_input_succeeds()`
- `test_create_session_with_duplicate_id_fails()`
- `test_atomic_increment_prevents_race_condition()`

## Performance Standards

### Code Performance

- **DynamoDB queries**: <50ms p99
- **Lambda cold start**: <1s (with provisioned concurrency if needed)
- **Audio processing**: <5% of real-time duration
- **Frontend bundle**: <500KB gzipped

### Optimization Priorities

1. **Critical Path**: Optimize latency-sensitive operations first
2. **Cost**: Optimize expensive operations (AWS API calls)
3. **Memory**: Keep Lambda memory usage efficient
4. **Bundle Size**: Frontend bundle affects load time

## Security Patterns

### Secrets Management

**Never**:
- Hard-code credentials
- Commit tokens to git
- Log sensitive data

**Instead**:
- Use IAM roles for Lambda
- Use Secrets Manager for secrets
- Use environment variables for config

### Input Validation

**Always validate**:
- Session IDs (format, existence)
- Language codes (ISO 639-1)
- User inputs (sanitize for XSS)
- Audio data (size, format)

**Pattern**:
```python
def validate_session_id(session_id: str) -> bool:
    pattern = r'^[a-z]+-[a-z]+-\d{3}$'
    if not re.match(pattern, session_id):
        raise ValidationError("Invalid session ID format")
    return True
```

## Monitoring & Observability

### CloudWatch Metrics

**Namespace**: `{Component}/{Feature}`

**Example**: `SessionManagement/Connections`

**Dimensions**: `SessionId`, `UserId`, `Language`, etc.

### Dashboard Organization

**One dashboard per component** with widgets for:
- Latency metrics (p50, p95, p99)
- Error rates
- Throughput
- Business metrics (sessions, listeners)

### Alerting Strategy

**Critical** (page on-call):
- System down
- Error rate >5%
- Latency >2x target

**Warning** (email):
- Error rate >2%
- Cost anomaly
- Cache hit rate <20%

## Code Review Checklist

**Before submitting PR**:
- [ ] Code follows naming conventions
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] Error handling implemented
- [ ] Logging added
- [ ] Performance acceptable
- [ ] Security reviewed
- [ ] No hardcoded values

**Reviewer checklist**:
- [ ] Requirements addressed
- [ ] Code is readable
- [ ] Tests are comprehensive
- [ ] Error handling is robust
- [ ] No security vulnerabilities
- [ ] Performance impact acceptable
