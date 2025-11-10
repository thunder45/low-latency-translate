"""
Setup script for session management package.
"""
from setuptools import setup, find_packages

setup(
    name="session-management",
    version="0.1.0",
    description="Session Management & WebSocket Infrastructure",
    packages=find_packages(exclude=["tests", "infrastructure"]),
    python_requires=">=3.11",
    install_requires=[
        "boto3>=1.28.85",
        "PyJWT>=2.8.0",
        "cryptography>=41.0.7",
        "requests>=2.31.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "moto>=4.2.9",
            "black>=23.11.0",
            "flake8>=6.1.0",
            "mypy>=1.7.1",
        ]
    },
)
