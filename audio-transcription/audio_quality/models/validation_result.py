"""
Validation result data model.

This module defines the ValidationResult dataclass for representing
the outcome of validation operations.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    
    success: bool
    errors: List[str]
    
    def __bool__(self) -> bool:
        """
        Allows ValidationResult to be used in boolean context.
        
        Returns:
            True if validation succeeded, False otherwise.
        """
        return self.success
    
    @property
    def error_message(self) -> str:
        """
        Gets a formatted error message combining all errors.
        
        Returns:
            Single string with all error messages joined by newlines.
            Empty string if no errors.
        """
        return '\n'.join(self.errors) if self.errors else ''
    
    @classmethod
    def success_result(cls) -> 'ValidationResult':
        """
        Creates a successful validation result.
        
        Returns:
            ValidationResult with success=True and empty errors.
        """
        return cls(success=True, errors=[])
    
    @classmethod
    def failure_result(cls, errors: List[str]) -> 'ValidationResult':
        """
        Creates a failed validation result.
        
        Args:
            errors: List of error messages.
            
        Returns:
            ValidationResult with success=False and provided errors.
        """
        return cls(success=False, errors=errors)
