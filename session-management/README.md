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
