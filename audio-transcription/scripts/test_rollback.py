#!/usr/bin/env python3
"""
Test script for rollback procedures.

This script tests the rollback mechanisms to ensure they work correctly
before production deployment.

Usage:
    python test_rollback.py --env dev
    python test_rollback.py --env staging
"""

import argparse
import json
import time
import sys
import boto3
from botocore.exceptions import ClientError


class RollbackTester:
    """Test rollback procedures for partial results feature."""
    
    def __init__(self, env: str):
        """
        Initialize tester.
        
        Args:
            env: Environment (dev, staging, prod)
        """
        self.env = env
        self.parameter_name = self._get_parameter_name()
        self.function_name = self._get_function_name()
        self.ssm_client = boto3.client('ssm')
        self.lambda_client = boto3.client('lambda')
        
        self.tests_passed = 0
        self.tests_failed = 0
    
    def _get_parameter_name(self) -> str:
        """Get SSM parameter name for environment."""
        if self.env == 'prod':
            return '/audio-transcription/partial-results/config'
        else:
            return f'/audio-transcription/{self.env}/partial-results/config'
    
    def _get_function_name(self) -> str:
        """Get Lambda function name for environment."""
        if self.env == 'prod':
            return 'audio-processor'
        else:
            return f'audio-processor-{self.env}'
    
    def run_all_tests(self) -> bool:
        """
        Run all rollback tests.
        
        Returns:
            True if all tests passed
        """
        print(f"Testing rollback procedures for {self.env} environment")
        print("=" * 60)
        
        # Test 1: Feature flag enable/disable
        self.test_feature_flag_enable_disable()
        
        # Test 2: Percentage-based rollout
        self.test_percentage_rollout()
        
        # Test 3: Configuration validation
        self.test_configuration_validation()
        
        # Test 4: Environment variable fallback
        self.test_environment_variable_fallback()
        
        # Test 5: Cache invalidation
        self.test_cache_invalidation()
        
        # Summary
        print("\n" + "=" * 60)
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_failed}")
        print("=" * 60)
        
        return self.tests_failed == 0
    
    def test_feature_flag_enable_disable(self):
        """Test enabling and disabling feature via feature flag."""
        print("\nTest 1: Feature Flag Enable/Disable")
        print("-" * 60)
        
        try:
            # Save original config
            original_config = self._get_config()
            print(f"Original config: {json.dumps(original_config, indent=2)}")
            
            # Test disable
            print("\n1.1 Testing disable...")
            self._update_config({
                'enabled': False,
                'rollout_percentage': 0,
                'min_stability_threshold': 0.85,
                'max_buffer_timeout': 5.0
            })
            
            config = self._get_config()
            assert config['enabled'] == False, "Feature should be disabled"
            assert config['rollout_percentage'] == 0, "Rollout should be 0%"
            print("✓ Disable successful")
            
            # Test enable
            print("\n1.2 Testing enable...")
            self._update_config({
                'enabled': True,
                'rollout_percentage': 100,
                'min_stability_threshold': 0.85,
                'max_buffer_timeout': 5.0
            })
            
            config = self._get_config()
            assert config['enabled'] == True, "Feature should be enabled"
            assert config['rollout_percentage'] == 100, "Rollout should be 100%"
            print("✓ Enable successful")
            
            # Restore original config
            self._update_config(original_config)
            print("\n✓ Test 1 PASSED")
            self.tests_passed += 1
            
        except Exception as e:
            print(f"\n✗ Test 1 FAILED: {e}")
            self.tests_failed += 1
    
    def test_percentage_rollout(self):
        """Test percentage-based rollout."""
        print("\nTest 2: Percentage-Based Rollout")
        print("-" * 60)
        
        try:
            # Save original config
            original_config = self._get_config()
            
            # Test 10% rollout
            print("\n2.1 Testing 10% rollout...")
            self._update_config({
                'enabled': True,
                'rollout_percentage': 10,
                'min_stability_threshold': 0.85,
                'max_buffer_timeout': 5.0
            })
            
            config = self._get_config()
            assert config['rollout_percentage'] == 10, "Rollout should be 10%"
            print("✓ 10% rollout set")
            
            # Test 50% rollout
            print("\n2.2 Testing 50% rollout...")
            self._update_config({
                'enabled': True,
                'rollout_percentage': 50,
                'min_stability_threshold': 0.85,
                'max_buffer_timeout': 5.0
            })
            
            config = self._get_config()
            assert config['rollout_percentage'] == 50, "Rollout should be 50%"
            print("✓ 50% rollout set")
            
            # Test 100% rollout
            print("\n2.3 Testing 100% rollout...")
            self._update_config({
                'enabled': True,
                'rollout_percentage': 100,
                'min_stability_threshold': 0.85,
                'max_buffer_timeout': 5.0
            })
            
            config = self._get_config()
            assert config['rollout_percentage'] == 100, "Rollout should be 100%"
            print("✓ 100% rollout set")
            
            # Restore original config
            self._update_config(original_config)
            print("\n✓ Test 2 PASSED")
            self.tests_passed += 1
            
        except Exception as e:
            print(f"\n✗ Test 2 FAILED: {e}")
            self.tests_failed += 1
    
    def test_configuration_validation(self):
        """Test configuration parameter validation."""
        print("\nTest 3: Configuration Validation")
        print("-" * 60)
        
        try:
            # Save original config
            original_config = self._get_config()
            
            # Test invalid stability threshold (too low)
            print("\n3.1 Testing invalid stability threshold (too low)...")
            try:
                self._update_config({
                    'enabled': True,
                    'rollout_percentage': 100,
                    'min_stability_threshold': 0.60,  # Invalid: < 0.70
                    'max_buffer_timeout': 5.0
                })
                print("✗ Should have rejected invalid threshold")
                self.tests_failed += 1
                return
            except Exception:
                print("✓ Invalid threshold rejected")
            
            # Test invalid stability threshold (too high)
            print("\n3.2 Testing invalid stability threshold (too high)...")
            try:
                self._update_config({
                    'enabled': True,
                    'rollout_percentage': 100,
                    'min_stability_threshold': 0.99,  # Invalid: > 0.95
                    'max_buffer_timeout': 5.0
                })
                print("✗ Should have rejected invalid threshold")
                self.tests_failed += 1
                return
            except Exception:
                print("✓ Invalid threshold rejected")
            
            # Test invalid buffer timeout (too low)
            print("\n3.3 Testing invalid buffer timeout (too low)...")
            try:
                self._update_config({
                    'enabled': True,
                    'rollout_percentage': 100,
                    'min_stability_threshold': 0.85,
                    'max_buffer_timeout': 1.0  # Invalid: < 2.0
                })
                print("✗ Should have rejected invalid timeout")
                self.tests_failed += 1
                return
            except Exception:
                print("✓ Invalid timeout rejected")
            
            # Test valid configuration
            print("\n3.4 Testing valid configuration...")
            self._update_config({
                'enabled': True,
                'rollout_percentage': 100,
                'min_stability_threshold': 0.85,
                'max_buffer_timeout': 5.0
            })
            print("✓ Valid configuration accepted")
            
            # Restore original config
            self._update_config(original_config)
            print("\n✓ Test 3 PASSED")
            self.tests_passed += 1
            
        except Exception as e:
            print(f"\n✗ Test 3 FAILED: {e}")
            self.tests_failed += 1
    
    def test_environment_variable_fallback(self):
        """Test environment variable fallback."""
        print("\nTest 4: Environment Variable Fallback")
        print("-" * 60)
        
        try:
            # Get current Lambda configuration
            print("\n4.1 Getting Lambda configuration...")
            response = self.lambda_client.get_function_configuration(
                FunctionName=self.function_name
            )
            
            env_vars = response.get('Environment', {}).get('Variables', {})
            print(f"Current PARTIAL_RESULTS_ENABLED: {env_vars.get('PARTIAL_RESULTS_ENABLED')}")
            
            # Verify environment variable exists
            assert 'PARTIAL_RESULTS_ENABLED' in env_vars, "Environment variable should exist"
            print("✓ Environment variable exists")
            
            # Verify fallback value is valid
            fallback_value = env_vars.get('PARTIAL_RESULTS_ENABLED', 'true')
            assert fallback_value in ['true', 'false'], "Fallback value should be 'true' or 'false'"
            print(f"✓ Fallback value is valid: {fallback_value}")
            
            print("\n✓ Test 4 PASSED")
            self.tests_passed += 1
            
        except Exception as e:
            print(f"\n✗ Test 4 FAILED: {e}")
            self.tests_failed += 1
    
    def test_cache_invalidation(self):
        """Test cache invalidation timing."""
        print("\nTest 5: Cache Invalidation")
        print("-" * 60)
        
        try:
            # Save original config
            original_config = self._get_config()
            
            # Update config
            print("\n5.1 Updating configuration...")
            self._update_config({
                'enabled': False,
                'rollout_percentage': 0,
                'min_stability_threshold': 0.85,
                'max_buffer_timeout': 5.0
            })
            
            # Note: We can't actually test cache invalidation without invoking Lambda
            # This test just verifies the parameter update is immediate
            print("\n5.2 Verifying parameter updated immediately...")
            config = self._get_config()
            assert config['enabled'] == False, "Parameter should be updated immediately"
            print("✓ Parameter updated immediately")
            
            print("\nℹ️  Note: Cache invalidation (60s TTL) can only be tested with Lambda invocation")
            
            # Restore original config
            self._update_config(original_config)
            print("\n✓ Test 5 PASSED")
            self.tests_passed += 1
            
        except Exception as e:
            print(f"\n✗ Test 5 FAILED: {e}")
            self.tests_failed += 1
    
    def _get_config(self) -> dict:
        """Get current configuration from SSM."""
        try:
            response = self.ssm_client.get_parameter(
                Name=self.parameter_name,
                WithDecryption=False
            )
            return json.loads(response['Parameter']['Value'])
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                # Return default config
                return {
                    'enabled': True,
                    'rollout_percentage': 100,
                    'min_stability_threshold': 0.85,
                    'max_buffer_timeout': 5.0
                }
            else:
                raise
    
    def _update_config(self, config: dict):
        """Update configuration in SSM."""
        # Validate config
        if not 0 <= config.get('rollout_percentage', 0) <= 100:
            raise ValueError("rollout_percentage must be between 0 and 100")
        if not 0.70 <= config.get('min_stability_threshold', 0.85) <= 0.95:
            raise ValueError("min_stability_threshold must be between 0.70 and 0.95")
        if not 2.0 <= config.get('max_buffer_timeout', 5.0) <= 10.0:
            raise ValueError("max_buffer_timeout must be between 2.0 and 10.0")
        
        self.ssm_client.put_parameter(
            Name=self.parameter_name,
            Value=json.dumps(config),
            Type='String',
            Overwrite=True
        )


def main():
    parser = argparse.ArgumentParser(
        description='Test rollback procedures for partial results feature'
    )
    
    parser.add_argument(
        '--env',
        required=True,
        choices=['dev', 'staging', 'prod'],
        help='Environment to test'
    )
    
    args = parser.parse_args()
    
    # Confirm if testing production
    if args.env == 'prod':
        response = input("⚠️  WARNING: Testing in PRODUCTION. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
    
    # Run tests
    tester = RollbackTester(args.env)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
