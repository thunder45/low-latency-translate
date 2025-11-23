#!/usr/bin/env python3
"""
CDK app for Audio Transcription infrastructure.

This app defines the infrastructure for the audio transcription component
with partial results processing support.
"""

import os
import aws_cdk as cdk
from stacks.audio_transcription_stack import AudioTranscriptionStack


app = cdk.App()

# Get environment from context or default to 'dev'
# Support both 'environment' and 'env' parameter names
env_name = app.node.try_get_context('environment') or app.node.try_get_context('env') or 'dev'

# Load environment-specific configuration
config_file = f'config/{env_name}.json'
if os.path.exists(config_file):
    with open(config_file, 'r') as f:
        import json
        config = json.load(f)
else:
    config = {}

# Create stack with environment-specific configuration
AudioTranscriptionStack(
    app,
    f'AudioTranscriptionStack-{env_name}',
    stack_name=f'audio-transcription-{env_name}',
    description=f'Audio Transcription infrastructure for {env_name} environment',
    env=cdk.Environment(
        account=config.get('account', os.getenv('CDK_DEFAULT_ACCOUNT')),
        region=config.get('region', 'us-east-1')
    ),
    env_name=env_name,
    config=config,
    tags={
        'Environment': env_name,
        'Component': 'AudioTranscription',
        'ManagedBy': 'CDK'
    }
)

app.synth()
