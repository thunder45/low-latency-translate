# Session Management & WebSocket Infrastructure - Overview

## What This Component Does

This component provides the foundation for real-time multilingual audio broadcasting by managing:

1. **Speaker Sessions**: Authenticated speakers create broadcasting sessions with memorable IDs
2. **Listener Connections**: Anonymous listeners join sessions to receive translated audio
3. **WebSocket Management**: Persistent bidirectional communication via AWS API Gateway
4. **Connection Lifecycle**: Handles connect, heartbeat, disconnect, and refresh events
5. **State Management**: Tracks sessions and connections in DynamoDB
6. **Rate Limiting**: Prevents abuse through configurable limits
7. **Long Sessions**: Supports unlimited duration through connection refresh

## Key Features

### Human-Readable Session IDs
- Format: `{adjective}-{noun}-{3-digit-number}`
- Example: `golden-eagle-427`
- Christian/Bible-themed vocabulary
- Easy to share verbally

### Scalability
- Serverless architecture (Lambda + DynamoDB)
- On-demand capacity
- Up to 500 listeners per session
- Automatic cleanup via TTL

### Resilience
- Connection refresh for sessions > 2 hours
- Heartbeat mechanism for connection health
- Graceful degradation on failures
- Idempotent operations

### Security
- JWT authentication for speakers
- TLS 1.2+ encryption (WSS)
- Rate limiting for abuse prevention
- No sensitive data logging

## Architecture at a Glance

```
Speaker (Authenticated)
    ↓ WSS + JWT
API Gateway WebSocket
    ↓
Lambda Authorizer → Cognito
    ↓
Connection Handler
    ↓
DynamoDB (Sessions, Connections)
    ↓
Listeners (Anonymous)
```

## Technology Stack

- **AWS Lambda**: Serverless compute (Python 3.11)
- **AWS API Gateway**: WebSocket API management
- **AWS DynamoDB**: NoSQL database for state
- **AWS Cognito**: User authentication (JWT)
- **AWS CDK**: Infrastructure as Code (Python)
- **AWS CloudWatch**: Logging and monitoring

## Project Organization

```
session-management/
├── infrastructure/     # AWS CDK code
├── lambda/            # Lambda function handlers
├── shared/            # Shared libraries
├── tests/             # Test files
└── docs/              # Documentation (this file)
```

## Documentation Guide

Start here based on your role:

### For Developers
1. **[QUICKSTART.md](QUICKSTART.md)** - Get running in 5 minutes
2. **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Understand the codebase
3. **[README.md](README.md)** - Architecture and development guide

### For DevOps/Deployment
1. **[DEPLOYMENT.md](DEPLOYMENT.md)** - Detailed deployment instructions
2. **[QUICKSTART.md](QUICKSTART.md)** - Quick deployment steps

### For Project Managers
1. **[TASK_1_SUMMARY.md](TASK_1_SUMMARY.md)** - What's been completed
2. **[OVERVIEW.md](OVERVIEW.md)** - This file

### For Architects
1. **[README.md](README.md)** - Architecture overview
2. **Design Document** - See `.kiro/specs/session-management-websocket/design.md`
3. **Requirements** - See `.kiro/specs/session-management-websocket/requirements.md`

## Current Status

✅ **Task 1 Complete**: Project structure and core infrastructure set up

### What's Ready
- Complete project structure (34 files)
- AWS CDK infrastructure code
- Lambda function placeholders
- Shared libraries structure
- Test infrastructure
- Environment configurations
- Comprehensive documentation

### What's Next
- Task 2: Implement DynamoDB data access layer
- Task 3: Implement Session ID generation
- Task 4: Implement Lambda Authorizer
- Tasks 5-9: Implement remaining handlers
- Task 10: Deploy WebSocket API
- Tasks 11-12: Add monitoring
- Task 13: Deploy to AWS
- Task 14: Create client examples

## Quick Commands

```bash
# Setup
make install

# Test
make test

# Deploy
make deploy-dev

# Clean
make clean
```

## Getting Help

- **Issues**: Check CloudWatch Logs
- **Configuration**: See `infrastructure/config/`
- **Architecture**: See design document in `.kiro/specs/`
- **API**: See requirements document in `.kiro/specs/`

## Contributing

1. Follow the task list in `.kiro/specs/session-management-websocket/tasks.md`
2. Write tests for new functionality
3. Update documentation as needed
4. Run `make lint` and `make format` before committing

## License

Internal project - see organization license.
