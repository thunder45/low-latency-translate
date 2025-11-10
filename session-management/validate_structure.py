#!/usr/bin/env python3
"""
Validate project structure is complete.
"""
import os
import sys

REQUIRED_FILES = [
    # Root files
    ".gitignore",
    "README.md",
    "DEPLOYMENT.md",
    "PROJECT_STRUCTURE.md",
    "requirements.txt",
    "setup.py",
    "Makefile",
    
    # Infrastructure
    "infrastructure/app.py",
    "infrastructure/cdk.json",
    "infrastructure/requirements.txt",
    "infrastructure/config/dev.json",
    "infrastructure/config/dev.json.example",
    "infrastructure/config/staging.json.example",
    "infrastructure/config/prod.json.example",
    "infrastructure/stacks/__init__.py",
    "infrastructure/stacks/session_management_stack.py",
    
    # Lambda functions
    "lambda/authorizer/__init__.py",
    "lambda/authorizer/handler.py",
    "lambda/connection_handler/__init__.py",
    "lambda/connection_handler/handler.py",
    "lambda/heartbeat_handler/__init__.py",
    "lambda/heartbeat_handler/handler.py",
    "lambda/disconnect_handler/__init__.py",
    "lambda/disconnect_handler/handler.py",
    "lambda/refresh_handler/__init__.py",
    "lambda/refresh_handler/handler.py",
    
    # Shared
    "shared/__init__.py",
    "shared/models/__init__.py",
    "shared/utils/__init__.py",
    "shared/config/__init__.py",
    "shared/config/constants.py",
    
    # Tests
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/test_placeholder.py",
]

def validate_structure():
    """Validate all required files exist."""
    missing_files = []
    
    for file_path in REQUIRED_FILES:
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        if not os.path.exists(full_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        return False
    
    print("✅ All required files present!")
    print(f"   Total files validated: {len(REQUIRED_FILES)}")
    return True

if __name__ == "__main__":
    success = validate_structure()
    sys.exit(0 if success else 1)
