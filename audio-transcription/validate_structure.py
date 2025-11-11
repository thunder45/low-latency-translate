#!/usr/bin/env python3
"""
Validate audio-transcription component structure.

This script verifies that all required files and directories exist
according to the project structure standards.
"""

import os
import sys
from pathlib import Path


def validate_structure():
    """Validate project structure."""
    errors = []
    warnings = []
    
    # Define required files and directories
    required_files = [
        # Root documentation
        'README.md',
        'OVERVIEW.md',
        'PROJECT_STRUCTURE.md',
        'QUICKSTART.md',
        'DEPLOYMENT.md',
        
        # Configuration
        'Makefile',
        'pytest.ini',
        'requirements.txt',
        'requirements-dev.txt',
        'setup.py',
        '.gitignore',
        
        # Lambda
        'lambda/__init__.py',
        'lambda/audio_processor/__init__.py',
        'lambda/audio_processor/handler.py',
        'lambda/audio_processor/requirements.txt',
        
        # Models
        'shared/models/__init__.py',
        'shared/models/cache.py',
        'shared/models/configuration.py',
        'shared/models/transcription_results.py',
        
        # Services
        'shared/services/__init__.py',
        'shared/services/deduplication_cache.py',
        'shared/services/feature_flag_service.py',
        'shared/services/final_result_handler.py',
        'shared/services/partial_result_handler.py',
        'shared/services/rate_limiter.py',
        'shared/services/result_buffer.py',
        'shared/services/sentence_boundary_detector.py',
        'shared/services/transcription_event_handler.py',
        'shared/services/translation_forwarder.py',
        
        # Utils
        'shared/utils/__init__.py',
        'shared/utils/metrics.py',
        'shared/utils/text_normalization.py',
        
        # Tests
        'tests/__init__.py',
        'tests/conftest.py',
        'tests/unit/__init__.py',
        'tests/unit/test_data_models.py',
        'tests/unit/test_deduplication_cache.py',
        'tests/unit/test_final_result_handler.py',
        'tests/unit/test_partial_result_handler.py',
        'tests/unit/test_rate_limiter.py',
        'tests/unit/test_result_buffer.py',
        'tests/unit/test_sentence_boundary_detector.py',
        'tests/unit/test_text_normalization.py',
        'tests/unit/test_transcription_event_handler.py',
        
        # Infrastructure
        'infrastructure/stacks/__init__.py',
        'infrastructure/stacks/audio_transcription_stack.py',
        'infrastructure/app.py',
        'infrastructure/cdk.json',
        'infrastructure/requirements.txt',
        'infrastructure/README.md',
        'infrastructure/config/dev.json.example',
        'infrastructure/config/staging.json.example',
        'infrastructure/config/prod.json.example',
        
        # Scripts
        'scripts/manage_rollout.py',
        'scripts/test_rollback.py',
        
        # Deployment documentation
        'docs/DEPLOYMENT_ROLLOUT_GUIDE.md',
        'docs/ROLLBACK_RUNBOOK.md',
        
        # Task summaries
        'docs/TASK_1_SUMMARY.md',
        'docs/TASK_2_SUMMARY.md',
        'docs/TASK_3_SUMMARY.md',
        'docs/TASK_4_SUMMARY.md',
        'docs/TASK_5_SUMMARY.md',
        'docs/TASK_6_SUMMARY.md',
        'docs/TASK_7_SUMMARY.md',
        'docs/TASK_8_SUMMARY.md',
        'docs/TASK_9_SUMMARY.md',
        'docs/TASK_10_SUMMARY.md',
        'docs/TASK_11_SUMMARY.md',
        'docs/TASK_12_SUMMARY.md',
        'docs/TASK_13_SUMMARY.md',
        'docs/TASK_14_SUMMARY.md',
        'docs/TASK_15_SUMMARY.md',
        'docs/TASK_16_SUMMARY.md',
    ]
    
    required_dirs = [
        'lambda',
        'lambda/audio_processor',
        'shared',
        'shared/models',
        'shared/services',
        'shared/utils',
        'tests',
        'tests/unit',
        'docs',
        'scripts',
        'infrastructure',
        'infrastructure/stacks',
        'infrastructure/config',
    ]
    
    # Check required directories
    for dir_path in required_dirs:
        full_path = Path(dir_path)
        if not full_path.exists():
            errors.append(f"Missing required directory: {dir_path}")
        elif not full_path.is_dir():
            errors.append(f"Path exists but is not a directory: {dir_path}")
    
    # Check required files
    for file_path in required_files:
        full_path = Path(file_path)
        if not full_path.exists():
            errors.append(f"Missing required file: {file_path}")
        elif not full_path.is_file():
            errors.append(f"Path exists but is not a file: {file_path}")
    
    # Check for common issues
    
    # Verify __init__.py files in all Python packages
    python_packages = [
        'lambda',
        'lambda/audio_processor',
        'shared',
        'shared/models',
        'shared/services',
        'shared/utils',
        'tests',
        'tests/unit',
        'infrastructure/stacks',
    ]
    
    for package in python_packages:
        init_file = Path(package) / '__init__.py'
        if not init_file.exists():
            warnings.append(f"Missing __init__.py in package: {package}")
    
    # Print results
    print("=" * 70)
    print("Audio Transcription - Structure Validation")
    print("=" * 70)
    print()
    
    if not errors and not warnings:
        print("✅ All checks passed!")
        print()
        print("Structure is valid and complete.")
        return 0
    
    if warnings:
        print("⚠️  Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
        print()
    
    if errors:
        print("❌ Errors:")
        for error in errors:
            print(f"  - {error}")
        print()
        print("Structure validation failed. Please fix the errors above.")
        return 1
    
    print("Structure validation passed with warnings.")
    return 0


if __name__ == '__main__':
    sys.exit(validate_structure())
