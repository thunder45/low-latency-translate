---
inclusion: always
---

# Test-Driven Task Workflow

## Pre-Task Requirements

Before starting any task:
1. Run all tests
2. Verify all tests pass with zero warnings
3. If tests fail, resolve issues before proceeding

## Post-Task Requirements

After completing any task:
1. Run all tests again to ensure no regressions
2. All tests must pass with zero warnings
3. Generate task summary documentation in `docs/TASK_<number>_SUMMARY.md`
4. Update root-level documentation as needed:
   - `README.md` - Add task summary links, update architecture if changed
   - `OVERVIEW.md` - Update status, features, or current state
   - `PROJECT_STRUCTURE.md` - Update file tree if files added/removed
   - `QUICKSTART.md` - Update if setup/deployment steps changed
   - `DEPLOYMENT.md` - Update if deployment procedures changed
5. Update `validate_structure.py` if new required files were added

## Task Summary Documentation

Create `<root_feature_folder>/docs/TASK_<number>_SUMMARY.md` (where "root_feature_folder" is something like "session-management") with:

### Required Sections

**Task Description**: Brief 1-2 sentence overview

**Task Instructions**: Detailed requirements and acceptance criteria

**Task Tests**: 
- List of test commands executed
- Test results (pass/fail counts)
- Coverage metrics if applicable

**Task Solution**:
- Key implementation decisions
- Code changes summary
- Files modified/created

### Example Structure

```markdown
# Task 15: Implement Feature X

## Task Description
Brief description of what was implemented.

## Task Instructions
Detailed requirements from specification.

## Task Tests
- `pytest tests/test_feature_x.py` - 12 passed
- `pytest tests/integration/` - 8 passed
- Coverage: 85%

## Task Solution
- Created `shared/services/feature_x.py`
- Modified `lambda/handler.py` to integrate feature
- Added validation logic for edge cases
```

## Workflow Summary

1. **Before**: Run tests, ensure clean baseline
2. **During**: Implement changes following TDD principles
3. **After**: Run tests, verify no regressions, document in `docs/TASK_<number>_SUMMARY.md`



# Team Coding Standards

## Code Style

### Python (PEP 8 + Enhancements)

**Line Length**: 88 characters (Black default)

**Indentation**: 4 spaces (no tabs)

**Quotes**: Double quotes for strings (consistent with Black)

**Type Hints**: Required for all functions
```python
def create_session(
    session_id: str,
    speaker_id: str,
    source_language: str
) -> Dict[str, Any]:
    """Create new session."""
    pass
```

**Docstrings**: Required for all public functions/classes (Google style)
```python
def function_name(param1: str) -> bool:
    """
    Brief description.
    
    Longer description if needed.
    
    Args:
        param1: Description
        
    Returns:
        Description
        
    Raises:
        ValueError: When invalid
    """
    pass
```

**Imports**: Sorted with `isort`
```python
# Standard library
import os
from typing import Dict

# Third-party
import boto3

# Local
from shared.models import Session
```

**Constants**: Uppercase at module level
```python
MAX_LISTENERS_PER_SESSION = 500
SESSION_MAX_DURATION_HOURS = 2
```

### TypeScript/React

**Line Length**: 100 characters

**Indentation**: 2 spaces

**Quotes**: Single quotes for strings

**Semicolons**: Required

**Type Annotations**: Required for all functions
```typescript
function createSession(
  sessionId: string,
  userId: string
): Promise<Session> {
  // Implementation
}
```

**Interfaces over Types** for object shapes:
```typescript
// Prefer
interface AudioState {
  isPaused: boolean;
  isMuted: boolean;
}

// Over
type AudioState = {
  isPaused: boolean;
  isMuted: boolean;
};
```

**React Components**: Functional with hooks
```typescript
interface Props {
  sessionId: string;
  onPause: () => void;
}

export function BroadcastControls({ sessionId, onPause }: Props) {
  const [isPaused, setIsPaused] = useState(false);
  
  return (
    <div>
      <button onClick={onPause}>Pause</button>
    </div>
  );
}
```

## Testing Standards

### Test Coverage

**Minimum**: 80% code coverage

**Priority Coverage**:
- Business logic: 100%
- Data access: 100%
- Error handling: 100%
- Happy paths: 100%
- Edge cases: >80%

### Test Organization

**AAA Pattern**: Arrange, Act, Assert

```python
def test_create_session_with_valid_input_succeeds():
    # Arrange
    session_id = 'test-session-123'
    mock_repo = Mock()
    
    # Act
    result = service.create_session(session_id)
    
    # Assert
    assert result['sessionId'] == session_id
    mock_repo.create_session.assert_called_once()
```

### Test Naming

**Pattern**: `test_{what}_{condition}_{expected}`

**Examples**:
- `test_create_session_with_valid_input_succeeds()`
- `test_join_session_with_inactive_session_fails()`
- `test_atomic_increment_with_race_condition_succeeds()`

### Mock Usage

**Prefer dependency injection** for testability:

```python
# Good - testable
class SessionService:
    def __init__(self, repository):
        self.repository = repository

# Test
def test_service():
    mock_repo = Mock()
    service = SessionService(mock_repo)
    # Test with mock
```

**Use `moto` for AWS service mocking**:
```python
@mock_dynamodb
def test_with_real_dynamodb():
    # Creates local DynamoDB
    # Tests with real AWS SDK calls
    pass
```

### Test Data

**Use fixtures** for reusable test data:

```python
@pytest.fixture
def valid_session_data():
    return {
        'sessionId': 'test-session-123',
        'speakerConnectionId': 'conn-123',
        'sourceLanguage': 'en',
        'listenerCount': 0
    }

def test_with_fixture(valid_session_data):
    # Use fixture
    result = create_session(**valid_session_data)
```

## Error Handling

### Exception Guidelines

**Create specific exceptions**:

```python
class SessionNotFoundError(ApplicationError):
    """Raised when session doesn't exist."""
    pass

class RateLimitExceededError(ApplicationError):
    """Raised when rate limit exceeded."""
    
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")
```

**Catch specific exceptions**:

```python
# Good
try:
    session = get_session(session_id)
except SessionNotFoundError:
    return error_response(404, "Session not found")
except DynamoDBError as e:
    logger.error(f"Database error: {e}")
    return error_response(500, "Internal error")

# Avoid
try:
    session = get_session(session_id)
except Exception as e:  # Too broad
    pass
```

### Error Messages

**User-facing**: Clear, actionable

```python
# Good
"Session not found. Please check the session ID."
"Audio distortion detected. Reduce microphone volume."

# Bad
"Error code 404"
"DynamoDB query failed"
```

**Logs**: Technical, detailed

```python
# Good
logger.error(
    f"Failed to query sessions table: {e}",
    extra={
        'session_id': session_id,
        'error_code': e.response['Error']['Code'],
        'request_id': context.request_id
    }
)

# Bad
logger.error("Error")
```

## Performance Guidelines

### Lambda Performance

**Cold Start Optimization**:
```python
# Initialize outside handler (reused across invocations)
dynamodb_client = DynamoDBClient()
sessions_repo = SessionsRepository(TABLE_NAME, dynamodb_client)

def lambda_handler(event, context):
    # Handler uses pre-initialized objects
    return sessions_repo.get_session(session_id)
```

**Memory Management**:
- Right-size Lambda memory (not too high, not too low)
- Monitor actual usage in CloudWatch
- Start with spec recommendation, adjust based on metrics

**Timeout Configuration**:
- Set timeout 2x expected duration
- Log warnings at 80% of timeout
- Alert if timeouts occur

### Database Performance

**DynamoDB Best Practices**:

```python
# Good - use projection to reduce data transfer
response = client.query(
    TableName='Connections',
    IndexName='sessionId-targetLanguage-index',
    KeyConditionExpression='sessionId = :sid',
    ProjectionExpression='connectionId, targetLanguage',  # Only needed fields
    ExpressionAttributeValues={':sid': session_id}
)

# Avoid - fetches all attributes
response = client.query(
    TableName='Connections',
    KeyConditionExpression='sessionId = :sid',
    ExpressionAttributeValues={':sid': session_id}
)
```

**Avoid N+1 Queries**:
```python
# Bad
for listener in listeners:
    connection = get_connection(listener.connection_id)  # N queries

# Good
connection_ids = [l.connection_id for l in listeners]
connections = batch_get_connections(connection_ids)  # 1 batch query
```

### Async/Await Usage

**Use async for I/O-bound operations**:

```python
# Good - parallel AWS API calls
async def translate_to_languages(text, languages):
    tasks = [translate_text(text, lang) for lang in languages]
    results = await asyncio.gather(*tasks)
    return dict(zip(languages, results))

# Bad - sequential
def translate_to_languages(text, languages):
    results = []
    for lang in languages:
        result = translate_text(text, lang)  # Blocking
        results.append(result)
    return results
```

## Security Standards

### Authentication

**Never**:
- Store passwords in plain text
- Log JWT tokens
- Include credentials in code

**Always**:
- Use IAM roles for AWS services
- Validate JWT signatures
- Check token expiration

### Input Validation

**Validate all inputs**:

```python
def validate_input(data: Dict) -> None:
    """Validate user input."""
    if 'sessionId' in data:
        validate_session_id(data['sessionId'])
    if 'targetLanguage' in data:
        validate_language_code(data['targetLanguage'])
```

**Sanitize for XSS**:

```typescript
// Frontend
function displayUserInput(text: string) {
  // Escape HTML
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return escaped;
}
```

### Data Protection

**PII Handling**:
- Don't log email addresses, IP addresses, or PII
- Hash connection IDs in logs
- No persistent storage of audio or transcripts

**Encryption**:
- TLS for all network communication
- Encrypted localStorage for tokens
- AWS-managed keys for DynamoDB (optional)

## Code Review Standards

### Review Process

**All code must be reviewed** before merge

**Reviewer Responsibilities**:
1. Verify requirements addressed
2. Check code quality and readability
3. Validate test coverage
4. Confirm error handling
5. Check for security issues
6. Approve or request changes

**Author Responsibilities**:
1. Self-review before requesting review
2. Provide context in PR description
3. Respond to feedback promptly
4. Update based on feedback

### Review Checklist

**Functionality**:
- [ ] Implements specified requirements
- [ ] Handles error cases
- [ ] Works as intended

**Code Quality**:
- [ ] Follows naming conventions
- [ ] Well-documented
- [ ] DRY (Don't Repeat Yourself)
- [ ] SOLID principles

**Testing**:
- [ ] Unit tests written
- [ ] Integration tests written (if applicable)
- [ ] All tests passing
- [ ] Coverage >80%

**Security**:
- [ ] Input validation
- [ ] No secrets in code
- [ ] Proper error messages (no info leak)

**Performance**:
- [ ] No obvious bottlenecks
- [ ] Efficient algorithms
- [ ] Appropriate caching

## Git Workflow

### Feature Development

```
1. Create feature branch from main
   git checkout -b feature/component-description

2. Implement feature with tests
   - Write tests first (TDD)
   - Implement functionality
   - Verify tests pass

3. Commit with conventional commit message
   git commit -m "feat(component): add feature X"

4. Push and create PR
   git push origin feature/component-description

5. Address review feedback

6. Merge to main (squash or merge commit)
```

### Hotfix Process

```
1. Create hotfix branch from main
   git checkout -b hotfix/critical-bug

2. Fix bug with test
   - Add test that reproduces bug
   - Fix bug
   - Verify test passes

3. Fast-track review (same day)

4. Deploy to staging, then production

5. Merge to main
```

## Communication Standards

### Code Comments

**When to comment**:
- Complex algorithms
- Non-obvious business rules
- Workarounds for known issues
- TODOs with context

```python
# Good - explains WHY
# Using 0.85 stability threshold based on accuracy analysis
# See: .kiro/specs/realtime-audio-transcription/design.md#stability
if stability_score >= 0.85:
    forward_to_translation(text)

# Bad - explains WHAT (code is self-documenting)
# Forward text to translation
forward_to_translation(text)
```

**TODO format**:
```python
# TODO(username): Brief description
# Context: Why this is needed
# Ticket: PROJ-123
```

### Pull Request Communication

**Title**: Clear and concise
```
feat(transcription): implement partial result processing
fix(session-mgmt): prevent negative listener count
```

**Description**: Context for reviewers
```markdown
## What
Implements partial result processing with stability thresholding

## Why
Reduces latency from 4-7s to 2-4s (Requirement 1, Criteria 1-5)

## How
- Stability-based forwarding (threshold: 0.85)
- Rate limiting (5/sec)
- Deduplication cache

## Testing
- Unit tests: 15 new tests, all passing
- Integration: End-to-end latency measured at 2.3s average
```

### Slack/Communication

**Channels** (suggested):
- `#low-latency-translate` - General discussion
- `#llt-dev` - Development questions
- `#llt-deployments` - Deployment notifications
- `#llt-incidents` - Production issues

**Daily Standup** (async in Slack or sync):
- What did you do yesterday?
- What will you do today?
- Any blockers?

## Documentation Standards

### README Structure

**Every component README** should have:

```markdown
# Component Name

Brief description (1-2 sentences)

## Overview
What this component does and why it exists

## Architecture
High-level design with diagrams

## Getting Started
How to set up and run locally

## Testing
How to run tests

## Deployment
How to deploy

## Troubleshooting
Common issues and solutions

## Contributing
How to contribute to this component
```

### Inline Documentation

**Module-level docstring**:
```python
"""
Session management repository.

This module provides repository pattern for Session entities in DynamoDB.
Includes atomic operations for listener count management and TTL handling.
"""
```

**Class-level docstring**:
```python
class SessionsRepository:
    """
    Repository for Session entities.
    
    Provides CRUD operations and atomic counter updates for sessions.
    Uses DynamoDBClient for all database operations.
    """
```

### API Documentation

**WebSocket messages** documented in component `docs/API.md`:

```markdown
## Message: sessionCreated

**Direction**: Server → Client

**Trigger**: After successful session creation

**Format**:
```json
{
  "type": "sessionCreated",
  "sessionId": "golden-eagle-427",
  ...
}
```

**Fields**:
- `sessionId` (string): Human-readable session identifier
- ...
```

## Collaboration Practices

### Pair Programming

**When to pair**:
- Complex features (emotion detection, connection refresh)
- Critical bug fixes
- Knowledge transfer

**How to pair**:
- Screen share with driver/navigator rotation (30-minute switches)
- Document decisions in code comments
- Both developers review before commit

### Code Ownership

**Component ownership**:
- Developer 1: Session Management, Infrastructure
- Developer 2: Audio Quality, Audio Dynamics
- Developer 3: Transcription, Translation
- Developer 4: Frontend

**But**: Everyone can contribute to any component

**Owner responsibilities**:
- Review PRs for their component
- Maintain documentation
- Monitor production metrics
- Resolve component-specific issues

### Knowledge Sharing

**Weekly tech talk** (30 minutes):
- Share interesting problems solved
- Discuss design decisions
- Demo new features

**Documentation**:
- Update specs when implementation differs
- Document workarounds
- Share learnings in `docs/LESSONS_LEARNED.md`

## Quality Gates

### Pre-Commit

**Run locally before commit**:
```bash
make format  # Auto-format code
make lint    # Check for issues
make test    # Run tests
```

**Git hooks** (optional):
- pre-commit: Run formatters
- pre-push: Run tests

### Pre-PR

**Checklist before creating PR**:
- [ ] All tests passing (`make test`)
- [ ] No linting errors (`make lint`)
- [ ] Code formatted (`make format`)
- [ ] Documentation updated
- [ ] Self-reviewed (read your own diff)

### Pre-Merge

**Requirements**:
- [ ] At least 1 approval
- [ ] All tests passing (CI)
- [ ] No merge conflicts
- [ ] Branch up to date with main

### Pre-Deploy

**Checklist before deployment**:
- [ ] All tests passing in staging
- [ ] Smoke tests completed
- [ ] Rollback plan documented
- [ ] Monitoring configured
- [ ] On-call notified

## Debugging Practices

### Logging for Debugging

**Add contextual logs**:

```python
logger.debug(
    f"Processing partial result",
    extra={
        'session_id': session_id,
        'stability': stability_score,
        'text_length': len(text),
        'result_id': result_id
    }
)
```

**Log at decision points**:
```python
if stability_score >= threshold:
    logger.debug(f"Forwarding partial result (stability={stability_score})")
    forward_to_translation(text)
else:
    logger.debug(f"Buffering partial result (stability={stability_score})")
    buffer_result(text)
```

### CloudWatch Insights Queries

**Example queries for common debugging**:

**Find errors in last hour**:
```
fields @timestamp, @message, level, error_code
| filter level = "ERROR"
| sort @timestamp desc
| limit 100
```

**Track session lifecycle**:
```
fields @timestamp, operation, session_id, message
| filter session_id = "golden-eagle-427"
| sort @timestamp asc
```

**Measure latency**:
```
fields @timestamp, operation, duration_ms
| stats avg(duration_ms), max(duration_ms), p99(duration_ms) by operation
```

### X-Ray Tracing (Optional)

**Add to critical paths**:
```python
from aws_xray_sdk.core import xray_recorder

@xray_recorder.capture('create_session')
def create_session(session_id, ...):
    # X-Ray will trace this function
    pass
```

## Performance Optimization

### Profiling

**Before optimizing**: Profile to find bottlenecks

**Python**:
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Code to profile
result = expensive_operation()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)  # Top 10 functions
```

**TypeScript/React**:
- Chrome DevTools Performance tab
- React DevTools Profiler
- Lighthouse audits

### Optimization Priorities

1. **Correctness First**: Never sacrifice correctness for performance
2. **Measure**: Profile before optimizing
3. **Low-Hanging Fruit**: Fix obvious issues first
4. **Critical Path**: Optimize latency-sensitive code
5. **Cost**: Optimize expensive operations (API calls)

### Common Optimizations

**Python**:
- Use `@lru_cache` for expensive pure functions
- Use list comprehensions over loops
- Use `asyncio.gather()` for parallel I/O

**TypeScript/React**:
- Use `React.memo()` for expensive components
- Debounce expensive operations (50-100ms)
- Lazy load non-critical components
- Code splitting for large bundles

## Security Practices

### Security Review

**Before production deployment**:
- [ ] Input validation on all user inputs
- [ ] No secrets in code or logs
- [ ] SQL/NoSQL injection prevention
- [ ] XSS prevention (frontend)
- [ ] CSRF protection (if applicable)
- [ ] Rate limiting implemented
- [ ] Error messages don't leak info

### Vulnerability Management

**Dependencies**:
- Run `pip-audit` (Python) or `npm audit` (TypeScript) weekly
- Update dependencies monthly
- Address critical vulnerabilities immediately

**Secrets Rotation**:
- Rotate Cognito client secrets quarterly
- Rotate AWS access keys (if any) monthly
- Update IAM role policies as needed

## Incident Response

### On-Call Responsibilities

**Response Times**:
- Critical (system down): 15 minutes
- High (degraded service): 1 hour
- Medium (partial failure): 4 hours
- Low (monitoring alert): Next business day

**On-Call Checklist**:
- [ ] Access to AWS console
- [ ] Access to monitoring dashboards
- [ ] Runbooks bookmarked
- [ ] Escalation contacts saved

### Incident Handling

**Steps**:
1. **Acknowledge**: Respond to alert within SLA
2. **Assess**: Determine severity and impact
3. **Mitigate**: Stop the bleeding (rollback, disable feature)
4. **Communicate**: Update stakeholders
5. **Resolve**: Fix root cause
6. **Document**: Write post-mortem

### Post-Mortem Template

```markdown
# Incident: [Brief description]

**Date**: YYYY-MM-DD
**Duration**: X hours
**Severity**: Critical/High/Medium/Low
**Impact**: [Users/features affected]

## Timeline
- HH:MM - Event occurred
- HH:MM - Alert triggered
- HH:MM - On-call responded
- HH:MM - Mitigation applied
- HH:MM - Resolved

## Root Cause
[Technical explanation]

## Resolution
[What fixed it]

## Action Items
- [ ] Prevent recurrence (e.g., add validation)
- [ ] Improve detection (e.g., better alert)
- [ ] Update runbook
```

## Meeting Standards

### Sprint Planning (Weekly)

**Duration**: 1 hour

**Agenda**:
1. Review last week's completed tasks
2. Demo completed features
3. Discuss blockers
4. Assign tasks for next week
5. Update roadmap if needed

**Outcome**: Each developer knows their tasks for the week

### Milestone Review (End of Each Week)

**Duration**: 30 minutes

**Agenda**:
1. Review milestone criteria
2. Demo milestone functionality
3. Discuss any gaps
4. Decision: proceed or extend

**Outcome**: Go/no-go for next phase

### Daily Standups (Optional)

**Duration**: 15 minutes (or async in Slack)

**Format**: What did you do? What will you do? Any blockers?

**Goal**: Keep team synchronized

## Continuous Improvement

### Retrospectives

**Frequency**: End of each phase (every 2-4 weeks)

**Duration**: 1 hour

**Format**: What went well? What didn't? What will we improve?

**Action Items**: Concrete changes for next phase

### Metrics Review

**Weekly**: Review key metrics
- Latency (are we meeting targets?)
- Error rates (are we stable?)
- Cost (are we on budget?)
- Velocity (are we on schedule?)

**Monthly**: Deep dive on trends

## Onboarding

### New Team Member Checklist

**Week 1**:
- [ ] Read all steering docs (.kiro/steering/)
- [ ] Review specifications for assigned component
- [ ] Set up development environment
- [ ] Run tests locally
- [ ] Deploy to dev environment

**Week 2**:
- [ ] Fix first bug or implement small feature
- [ ] Submit first PR
- [ ] Complete code review

**Week 3+**:
- [ ] Take on larger feature
- [ ] Participate in milestone review
- [ ] Begin reviewing others' PRs

### Knowledge Transfer

**Documentation-first**:
- Everything in code or documentation
- No undocumented tribal knowledge
- Update docs when implementation differs from spec

**Shadowing**:
- New members shadow experienced developers
- Pair programming for first week
- Gradually increase independence

## Tools & Environment

### Required Tools

**Development**:
- Python 3.11+ (pyenv recommended)
- Node 18+ (nvm recommended)
- AWS CLI v2
- Git
- VS Code or similar IDE

**Testing**:
- pytest (Python)
- Jest (TypeScript)
- Playwright (E2E)

**Deployment**:
- AWS CDK CLI
- Make
- Docker (optional, for local testing)

### IDE Configuration

**VS Code Extensions** (recommended):
- Python (Microsoft)
- Pylance
- ESLint
- Prettier
- GitLens
- AWS Toolkit

**Settings** (`.vscode/settings.json`):
```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "editor.formatOnSave": true,
  "python.formatting.provider": "black",
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```

## Definition of Done

### Feature Completion Criteria

**A feature is "done" when**:
- [ ] Code implemented per specification
- [ ] Unit tests written and passing (>80% coverage)
- [ ] Integration tests written and passing (if applicable)
- [ ] Documentation updated
- [ ] Code reviewed and approved
- [ ] Deployed to dev environment
- [ ] Manual testing completed
- [ ] Performance validated (meets targets)
- [ ] Security reviewed
- [ ] Merged to main

**Not done until ALL criteria met**

### Sprint Completion Criteria

**A sprint is "complete" when**:
- [ ] All planned tasks completed (or explicitly deprioritized)
- [ ] All tests passing in dev
- [ ] Milestone criteria validated
- [ ] Documentation updated
- [ ] Demo delivered to stakeholders

## Anti-Patterns to Avoid

### Code Anti-Patterns

❌ **God Objects**: Classes doing too much
✅ **Single Responsibility**: Each class has one purpose

❌ **Tight Coupling**: Direct dependencies everywhere
✅ **Dependency Injection**: Pass dependencies to constructor

❌ **Magic Numbers**: Hardcoded values in code
✅ **Named Constants**: `MAX_LISTENERS_PER_SESSION = 500`

❌ **Nested Conditionals**: Deep if/else chains
✅ **Early Returns**: Return early from invalid cases

### Architecture Anti-Patterns

❌ **Big Ball of Mud**: No clear structure
✅ **Layered Architecture**: Repository → Service → Handler

❌ **Premature Optimization**: Optimizing before measuring
✅ **Profile First**: Measure, then optimize bottlenecks

❌ **Not Invented Here**: Reimplementing everything
✅ **Use Libraries**: Leverage boto3, librosa, etc.

### Process Anti-Patterns

❌ **No Tests**: "I'll add tests later"
✅ **TDD**: Write tests first

❌ **No Reviews**: Merge without approval
✅ **Peer Review**: All code reviewed

❌ **No Documentation**: "Code is self-documenting"
✅ **Document**: Especially non-obvious decisions

## Questions & Support

**Technical Questions**: Ask in `#llt-dev` Slack channel

**Specification Questions**: Reference `.kiro/specs/` documents

**Architecture Questions**: Discuss in sprint planning or ad-hoc

**Urgent Issues**: Escalate to team lead

**Remember**: No question is too simple. Better to ask than assume!
