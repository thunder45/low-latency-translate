"""
Setup configuration for audio-transcription component.
"""

from setuptools import setup, find_packages

setup(
    name='audio-transcription',
    version='1.0.0',
    description='Real-time audio transcription with partial results processing',
    author='Low Latency Translate Team',
    packages=find_packages(exclude=['tests', 'tests.*']),
    python_requires='>=3.11',
    install_requires=[
        'boto3>=1.28.0',
        'botocore>=1.31.0',
        'librosa>=0.10.0',
        'numpy>=1.24.0',
        'soundfile>=0.12.0',
        'PyJWT>=2.8.0',
        'cryptography>=41.0.0',
        'requests>=2.31.0',
        'python-Levenshtein>=0.21.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'pytest-asyncio>=0.21.0',
            'pytest-cov>=4.1.0',
            'moto>=4.2.0',
            'pylint>=2.17.0',
            'flake8>=6.0.0',
            'black>=23.0.0',
            'mypy>=1.4.0',
        ]
    }
)
