#!/usr/bin/env python3
"""
AWS CDK App for Translation Broadcasting Pipeline Infrastructure.
"""
import os
import json
from aws_cdk import App, Environment
from stacks.translation_pipeline_stack import TranslationPipelineStack

app = App()

# Get environment from context (default to dev)
env_name = app.node.try_get_context("env") or "dev"

# Load environment-specific configuration
config_path = os.path.join(os.path.dirname(__file__), "config", f"{env_name}.json")
with open(config_path, "r") as f:
    config = json.load(f)

# Create stack
TranslationPipelineStack(
    app,
    f"TranslationPipeline-{env_name}",
    env=Environment(
        account=config.get("account"),
        region=config.get("region", "us-east-1")
    ),
    config=config,
    env_name=env_name
)

app.synth()
