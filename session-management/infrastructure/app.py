#!/usr/bin/env python3
"""
AWS CDK App for Session Management Infrastructure.
"""
import os
import sys
import json
from aws_cdk import App, Environment
from stacks.session_management_stack import SessionManagementStack
from stacks.http_api_stack import HttpApiStack

# Add audio-transcription infrastructure to path for cross-stack reference
audio_transcription_infra_path = os.path.join(
    os.path.dirname(__file__),
    "../../audio-transcription/infrastructure"
)
sys.path.insert(0, audio_transcription_infra_path)

try:
    from stacks.audio_transcription_stack import AudioTranscriptionStack
    audio_transcription_available = True
except ImportError:
    audio_transcription_available = False
    print("Warning: AudioTranscriptionStack not available. sendAudio route will not be configured.")

app = App()

# Get environment from context (default to dev)
# Support both 'env' and 'environment' parameter names for consistency
env_name = app.node.try_get_context("env") or app.node.try_get_context("environment") or "dev"

# Load environment-specific configuration
config_path = os.path.join(os.path.dirname(__file__), "config", f"{env_name}.json")
with open(config_path, "r") as f:
    config = json.load(f)

# Create environment
env = Environment(
    account=config.get("account"),
    region=config.get("region", "us-east-1")
)

# Create AudioTranscriptionStack first (if available)
audio_transcription_stack = None
if audio_transcription_available:
    audio_transcription_stack = AudioTranscriptionStack(
        app,
        f"AudioTranscription-{env_name}",
        env=env
    )

# Create SessionManagementStack with reference to AudioTranscriptionStack
session_management_stack = SessionManagementStack(
    app,
    f"SessionManagement-{env_name}",
    env=env,
    config=config,
    env_name=env_name,
    audio_transcription_stack=audio_transcription_stack
)

# Add dependency to ensure AudioTranscriptionStack is created first
if audio_transcription_stack:
    session_management_stack.add_dependency(audio_transcription_stack)

# Create HttpApiStack for session management HTTP API
http_api_stack = HttpApiStack(
    app,
    f"SessionHttpApi-{env_name}",
    sessions_table=session_management_stack.sessions_table,
    connections_table=session_management_stack.connections_table,
    user_pool=session_management_stack.user_pool,
    shared_layer=session_management_stack.shared_layer,
    env_name=env_name,
    config=config,
    env=env,
)

# Add dependency to ensure SessionManagementStack is created first
http_api_stack.add_dependency(session_management_stack)

app.synth()
