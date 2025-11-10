# Project Structure

```
session-management/
├── .gitignore                          # Git ignore patterns
├── README.md                           # Project overview and setup
├── DEPLOYMENT.md                       # Deployment guide
├── PROJECT_STRUCTURE.md                # This file
├── requirements.txt                    # Python dependencies
├── setup.py                            # Package setup configuration
├── Makefile                            # Build and deployment commands
│
├── infrastructure/                     # AWS CDK Infrastructure as Code
│   ├── app.py                         # CDK app entry point
│   ├── cdk.json                       # CDK configuration
│   ├── requirements.txt               # CDK dependencies
│   ├── config/                        # Environment-specific configs
│   │   ├── dev.json                   # Development environment
│   │   ├── dev.json.example           # Development template
│   │   ├── staging.json.example       # Staging template
│   │   └── prod.json.example          # Production template
│   └── stacks/                        # CDK stack definitions
│       ├── __init__.py
│       └── session_management_stack.py # Main infrastructure stack
│
├── lambda/                            # Lambda function handlers
│   ├── authorizer/                    # JWT token validation
│   │   ├── __init__.py
│   │   └── handler.py                 # Authorizer Lambda handler
│   ├── connection_handler/            # WebSocket $connect handler
│   │   ├── __init__.py
│   │   └── handler.py                 # Connection Lambda handler
│   ├── heartbeat_handler/             # Heartbeat message handler
│   │   ├── __init__.py
│   │   └── handler.py                 # Heartbeat Lambda handler
│   ├── disconnect_handler/            # WebSocket $disconnect handler
│   │   ├── __init__.py
│   │   └── handler.py                 # Disconnect Lambda handler
│   └── refresh_handler/               # Connection refresh handler
│       ├── __init__.py
│       └── handler.py                 # Refresh Lambda handler
│
├── shared/                            # Shared libraries and utilities
│   ├── __init__.py
│   ├── models/                        # Data models
│   │   └── __init__.py
│   ├── utils/                         # Utility functions
│   │   └── __init__.py
│   └── config/                        # Shared configuration
│       ├── __init__.py
│       └── constants.py               # Application constants
│
└── tests/                             # Test files
    ├── __init__.py
    ├── conftest.py                    # Pytest configuration
    └── test_placeholder.py            # Placeholder test

```

## Directory Descriptions

### `/infrastructure`
Contains AWS CDK code for deploying all infrastructure resources including:
- DynamoDB tables (Sessions, Connections, RateLimits)
- Lambda functions
- API Gateway WebSocket API
- IAM roles and policies
- CloudWatch log groups

### `/lambda`
Contains individual Lambda function handlers:
- **authorizer**: Validates JWT tokens from AWS Cognito
- **connection_handler**: Handles WebSocket $connect events (session creation and listener joining)
- **heartbeat_handler**: Responds to heartbeat messages and checks connection duration
- **disconnect_handler**: Handles WebSocket $disconnect events and cleanup
- **refresh_handler**: Handles connection refresh for long-running sessions

### `/shared`
Contains shared code used across multiple Lambda functions:
- **models**: Data models for sessions, connections, and rate limits
- **utils**: Utility functions (DynamoDB operations, validation, etc.)
- **config**: Shared constants and configuration values

### `/tests`
Contains test files for unit and integration testing:
- **conftest.py**: Pytest fixtures and configuration
- Test files will be added in subsequent tasks

## Configuration Files

- **requirements.txt**: Python dependencies for Lambda functions
- **setup.py**: Package configuration for local development
- **Makefile**: Convenient commands for common tasks
- **infrastructure/config/*.json**: Environment-specific configuration

## Next Steps

1. Implement Lambda function logic (tasks 2-9)
2. Add comprehensive tests (tasks marked with *)
3. Deploy infrastructure (task 13)
4. Create client examples (task 14)
