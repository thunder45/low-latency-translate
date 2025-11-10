# Session Management & WebSocket Infrastructure

This component provides the core session management and WebSocket infrastructure for the real-time multilingual audio broadcasting system.

📖 **New here?** Start with [OVERVIEW.md](OVERVIEW.md) for a high-level introduction.

## Architecture

- **Lambda Functions**: Serverless handlers for WebSocket lifecycle events
- **DynamoDB**: Session and connection state storage
- **API Gateway**: WebSocket API management
- **AWS CDK**: Infrastructure as Code

## Project Structure

```
session-management/
├── infrastructure/          # AWS CDK infrastructure code
│   ├── app.py              # CDK app entry point
│   ├── stacks/             # CDK stack definitions
│   └── config/             # Environment-specific configurations
├── lambda/                 # Lambda function code
│   ├── authorizer/         # JWT token validation
│   ├── connection_handler/ # WebSocket connect handler
│   ├── heartbeat_handler/  # Heartbeat message handler
│   ├── disconnect_handler/ # WebSocket disconnect handler
│   └── refresh_handler/    # Connection refresh handler
├── shared/                 # Shared libraries and utilities
│   ├── models/             # Data models
│   ├── utils/              # Utility functions
│   └── config/             # Shared configuration
└── tests/                  # Test files
```

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for a 5-minute setup guide.

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Setup

1. Install dependencies:
```bash
cd session-management
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp infrastructure/config/dev.json.example infrastructure/config/dev.json
# Edit dev.json with your configuration
```

3. Deploy infrastructure:
```bash
cd infrastructure
cdk bootstrap  # First time only
cdk deploy --context env=dev
```

## Development

- **Lambda Functions**: Located in `lambda/` directory
- **Shared Code**: Located in `shared/` directory
- **Infrastructure**: Located in `infrastructure/` directory

## Testing

```bash
pytest tests/
```

## Environment Variables

See `infrastructure/config/` for environment-specific configurations.

## Task Implementation Summaries

Detailed summaries of completed implementation tasks:

- [Task 1: Set up project structure and core infrastructure](TASK_1_SUMMARY.md)
- [Task 2: Implement DynamoDB tables and data access layer](TASK_2_SUMMARY.md)
- [Task 3: Implement Session ID generation](TASK_3_SUMMARY.md)
- [Task 4: Implement Lambda Authorizer](TASK_4_SUMMARY.md)
- [Task 5: Implement rate limiting](TASK_5_SUMMARY.md)
- [Task 6: Implement Connection Handler Lambda](TASK_6_SUMMARY.md)
- [Task 7: Implement Connection Refresh Handler Lambda](TASK_7_SUMMARY.md)
- [Task 8: Implement Heartbeat Handler Lambda](TASK_8_SUMMARY.md)
- [Task 9: Implement Disconnect Handler Lambda](TASK_9_SUMMARY.md)
- [Task 10: Implement API Gateway WebSocket API](TASK_10_SUMMARY.md)
- [Task 11: Implement monitoring and logging](TASK_11_SUMMARY.md)
- [Task 12: Implement error handling and resilience](TASK_12_SUMMARY.md)
