#!/usr/bin/env python3
"""
Script to manage gradual rollout of partial results feature.

This script updates the SSM parameter to control the rollout percentage
for canary deployment (10% → 50% → 100%).

Usage:
    python manage_rollout.py --percentage 10  # Start with 10%
    python manage_rollout.py --percentage 50  # Increase to 50%
    python manage_rollout.py --percentage 100 # Full rollout
    python manage_rollout.py --disable        # Emergency disable
    python manage_rollout.py --status         # Check current status
"""

import argparse
import json
import sys
import boto3
from botocore.exceptions import ClientError


def get_current_config(ssm_client, parameter_name: str) -> dict:
    """
    Get current feature flag configuration.
    
    Args:
        ssm_client: Boto3 SSM client
        parameter_name: SSM parameter name
        
    Returns:
        Current configuration as dictionary
    """
    try:
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=False
        )
        return json.loads(response['Parameter']['Value'])
    except ClientError as e:
        if e.response['Error']['Code'] == 'ParameterNotFound':
            print(f"Parameter {parameter_name} not found. Creating with defaults.")
            return {
                'enabled': True,
                'rollout_percentage': 0,
                'min_stability_threshold': 0.85,
                'max_buffer_timeout': 5.0
            }
        else:
            raise


def update_config(ssm_client, parameter_name: str, config: dict) -> None:
    """
    Update feature flag configuration.
    
    Args:
        ssm_client: Boto3 SSM client
        parameter_name: SSM parameter name
        config: New configuration dictionary
    """
    ssm_client.put_parameter(
        Name=parameter_name,
        Value=json.dumps(config),
        Type='String',
        Overwrite=True,
        Description='Feature flag configuration for partial results processing'
    )


def set_rollout_percentage(percentage: int, parameter_name: str) -> None:
    """
    Set rollout percentage for gradual deployment.
    
    Args:
        percentage: Rollout percentage (0-100)
        parameter_name: SSM parameter name
    """
    if not 0 <= percentage <= 100:
        print(f"Error: Percentage must be between 0 and 100, got {percentage}")
        sys.exit(1)
    
    ssm_client = boto3.client('ssm')
    
    # Get current config
    config = get_current_config(ssm_client, parameter_name)
    
    # Update rollout percentage
    old_percentage = config.get('rollout_percentage', 0)
    config['rollout_percentage'] = percentage
    
    # Update parameter
    update_config(ssm_client, parameter_name, config)
    
    print(f"✓ Rollout percentage updated: {old_percentage}% → {percentage}%")
    print(f"  Partial results will be enabled for {percentage}% of sessions")
    
    if percentage == 0:
        print("  ⚠️  WARNING: 0% rollout means partial results disabled for all new sessions")
    elif percentage == 100:
        print("  ✓ Full rollout: Partial results enabled for all sessions")
    else:
        print(f"  ℹ️  Canary deployment: {percentage}% of sessions will use partial results")


def disable_feature(parameter_name: str) -> None:
    """
    Emergency disable of partial results feature.
    
    Args:
        parameter_name: SSM parameter name
    """
    ssm_client = boto3.client('ssm')
    
    # Get current config
    config = get_current_config(ssm_client, parameter_name)
    
    # Disable feature
    config['enabled'] = False
    config['rollout_percentage'] = 0
    
    # Update parameter
    update_config(ssm_client, parameter_name, config)
    
    print("✓ Partial results feature DISABLED")
    print("  All sessions will fall back to final-result-only mode")
    print("  This change takes effect within 60 seconds (cache TTL)")


def enable_feature(parameter_name: str, percentage: int = 100) -> None:
    """
    Enable partial results feature.
    
    Args:
        parameter_name: SSM parameter name
        percentage: Initial rollout percentage
    """
    ssm_client = boto3.client('ssm')
    
    # Get current config
    config = get_current_config(ssm_client, parameter_name)
    
    # Enable feature
    config['enabled'] = True
    config['rollout_percentage'] = percentage
    
    # Update parameter
    update_config(ssm_client, parameter_name, config)
    
    print(f"✓ Partial results feature ENABLED")
    print(f"  Rollout percentage: {percentage}%")
    print("  This change takes effect within 60 seconds (cache TTL)")


def show_status(parameter_name: str) -> None:
    """
    Show current feature flag status.
    
    Args:
        parameter_name: SSM parameter name
    """
    ssm_client = boto3.client('ssm')
    
    try:
        config = get_current_config(ssm_client, parameter_name)
        
        print("Current Feature Flag Configuration:")
        print("=" * 50)
        print(f"  Enabled: {config.get('enabled', False)}")
        print(f"  Rollout Percentage: {config.get('rollout_percentage', 0)}%")
        print(f"  Min Stability Threshold: {config.get('min_stability_threshold', 0.85)}")
        print(f"  Max Buffer Timeout: {config.get('max_buffer_timeout', 5.0)}s")
        print("=" * 50)
        
        # Interpretation
        if not config.get('enabled', False):
            print("\n⚠️  Feature is DISABLED - all sessions use final-result-only mode")
        elif config.get('rollout_percentage', 0) == 0:
            print("\n⚠️  Rollout at 0% - partial results disabled for all sessions")
        elif config.get('rollout_percentage', 0) == 100:
            print("\n✓ Full rollout - partial results enabled for all sessions")
        else:
            percentage = config.get('rollout_percentage', 0)
            print(f"\nℹ️  Canary deployment - {percentage}% of sessions use partial results")
        
    except Exception as e:
        print(f"Error fetching status: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Manage gradual rollout of partial results feature'
    )
    
    parser.add_argument(
        '--parameter-name',
        default='/audio-transcription/partial-results/config',
        help='SSM parameter name (default: /audio-transcription/partial-results/config)'
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--percentage',
        type=int,
        help='Set rollout percentage (0-100)'
    )
    group.add_argument(
        '--disable',
        action='store_true',
        help='Emergency disable partial results feature'
    )
    group.add_argument(
        '--enable',
        action='store_true',
        help='Enable partial results feature'
    )
    group.add_argument(
        '--status',
        action='store_true',
        help='Show current feature flag status'
    )
    
    parser.add_argument(
        '--enable-percentage',
        type=int,
        default=100,
        help='Rollout percentage when using --enable (default: 100)'
    )
    
    args = parser.parse_args()
    
    try:
        if args.status:
            show_status(args.parameter_name)
        elif args.disable:
            disable_feature(args.parameter_name)
        elif args.enable:
            enable_feature(args.parameter_name, args.enable_percentage)
        elif args.percentage is not None:
            set_rollout_percentage(args.percentage, args.parameter_name)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
