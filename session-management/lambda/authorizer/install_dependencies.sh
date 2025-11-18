#!/bin/bash
# Install PyJWT dependencies locally for Lambda packaging

set -e

echo "Installing PyJWT dependencies for Lambda authorizer..."

# Install dependencies to local directory
pip install -r requirements.txt -t .

echo "Dependencies installed successfully!"
echo "Files in current directory:"
ls -la

