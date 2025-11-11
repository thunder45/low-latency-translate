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

## Getting Started

Choose the guide that fits your needs:

- 🚀 **[QUICKSTART.md](QUICKSTART.md)** - First-time setup (5 minutes, tutorial-style)
- 📋 **[DEPLOYMENT_QUICK_REFERENCE.md](DEPLOYMENT_QUICK_REFERENCE.md)** - Command cheat sheet (for experienced users)
- 📖 **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide (comprehensive documentation)
- ✅ **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Step-by-step verification checklist

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

## Deployment

For comprehensive deployment instructions, see:
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide with verification steps
- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Step-by-step deployment checklist
- **[DEPLOYMENT_QUICK_REFERENCE.md](DEPLOYMENT_QUICK_REFERENCE.md)** - Quick command reference

### Quick Deploy

```bash
# Configure environment
cp infrastructure/config/dev.json.example infrastructure/config/dev.json
# Edit dev.json with your AWS account details

# Deploy to development
make deploy-dev

# Verify deployment
aws dynamodb list-tables --region us-east-1
aws lambda list-functions --region us-east-1 | grep session
```

## Task Implementation Summaries

Detailed summaries of completed implementation tasks:

- [Task 1: Set up project structure and core infrastructure](docs/TASK_1_SUMMARY.md)
- [Task 2: Implement DynamoDB tables and data access layer](docs/TASK_2_SUMMARY.md)
- [Task 3: Implement Session ID generation](docs/TASK_3_SUMMARY.md)
- [Task 4: Implement Lambda Authorizer](docs/TASK_4_SUMMARY.md)
- [Task 5: Implement rate limiting](docs/TASK_5_SUMMARY.md)
- [Task 6: Implement Connection Handler Lambda](docs/TASK_6_SUMMARY.md)
- [Task 7: Implement Connection Refresh Handler Lambda](docs/TASK_7_SUMMARY.md)
- [Task 8: Implement Heartbeat Handler Lambda](docs/TASK_8_SUMMARY.md)
- [Task 9: Implement Disconnect Handler Lambda](docs/TASK_9_SUMMARY.md)
- [Task 10: Implement API Gateway WebSocket API](docs/TASK_10_SUMMARY.md)
- [Task 11: Implement monitoring and logging](docs/TASK_11_SUMMARY.md)
- [Task 12: Implement error handling and resilience](docs/TASK_12_SUMMARY.md)
- [Task 13: Deploy infrastructure](docs/TASK_13_SUMMARY.md)
- [Task 14: Create deployment documentation](docs/TASK_14_SUMMARY.md)
