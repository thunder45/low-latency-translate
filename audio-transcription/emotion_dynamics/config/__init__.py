"""
Configuration module for emotion dynamics detection and SSML generation.

Provides environment variable loading and feature flag management.
"""

from .settings import Settings, get_settings

__all__ = ['Settings', 'get_settings']
