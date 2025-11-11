"""
Setup script for Session Management & WebSocket Infrastructure package.

This package provides the core session management and WebSocket infrastructure
for the real-time multilingual audio broadcasting system.
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="session-management",
    version="1.0.0",
    author="Low Latency Translation Team",
    description="Session Management & WebSocket Infrastructure for Real-Time Translation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/low-latency-translate",
    packages=find_packages(exclude=["tests", "tests.*", "infrastructure", "infrastructure.*", "examples", "examples.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Communications",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
    install_requires=[
        # AWS SDK
        "boto3>=1.28.85",
        "botocore>=1.31.85",
        
        # Authentication
        "PyJWT>=2.8.0",
        "cryptography>=41.0.7",
        
        # HTTP client
        "requests>=2.31.0",
    ],
    extras_require={
        "dev": [
            # Testing
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
            "moto>=4.2.9",
            
            # Code quality
            "black>=23.11.0",
            "flake8>=6.1.0",
            "mypy>=1.7.1",
            
            # Type stubs
            "boto3-stubs[dynamodb,cognito-idp,apigatewaymanagementapi]>=1.28.85",
        ],
        "cdk": [
            # Infrastructure as Code
            "aws-cdk-lib>=2.100.0",
            "constructs>=10.0.0,<11.0.0",
        ],
        "examples": [
            # Client examples
            "websockets>=11.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "validate-structure=validate_structure:validate_structure",
        ],
    },
    include_package_data=True,
    package_data={
        "shared.config": ["*.txt"],
    },
    zip_safe=False,
)
