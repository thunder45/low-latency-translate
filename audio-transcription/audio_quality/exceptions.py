"""
Custom exceptions for audio quality validation.

This module defines custom exception classes for audio quality validation
errors, providing specific error types for different failure scenarios.
"""


class AudioQualityError(Exception):
    """
    Base exception for audio quality validation errors.
    
    All audio quality-specific exceptions inherit from this base class,
    allowing for easy catching of all audio quality-related errors.
    """
    pass


class AudioFormatError(AudioQualityError):
    """
    Raised when audio format is invalid or unsupported.
    
    This exception is raised when:
    - Audio format validation fails
    - Sample rate is not supported
    - Bit depth is not supported
    - Channel count is not supported
    - Audio encoding is not supported
    
    Attributes:
        message: Error message describing the format issue
        format_details: Optional dict with format details
    
    Examples:
        >>> raise AudioFormatError("Unsupported sample rate: 11025 Hz")
        >>> raise AudioFormatError(
        ...     "Invalid format",
        ...     format_details={'sample_rate': 11025, 'expected': [8000, 16000, 24000, 48000]}
        ... )
    """
    
    def __init__(self, message: str, format_details: dict = None):
        """
        Initialize AudioFormatError.
        
        Args:
            message: Error message
            format_details: Optional dict with format details
        """
        super().__init__(message)
        self.format_details = format_details or {}


class QualityAnalysisError(AudioQualityError):
    """
    Raised when quality analysis fails.
    
    This exception is raised when:
    - SNR calculation fails
    - Clipping detection fails
    - Echo detection fails
    - Silence detection fails
    - Any other analysis operation fails
    
    Attributes:
        message: Error message describing the analysis failure
        analysis_type: Type of analysis that failed (e.g., 'snr', 'clipping')
        original_error: Original exception that caused the failure (if any)
    
    Examples:
        >>> raise QualityAnalysisError("SNR calculation failed", analysis_type='snr')
        >>> try:
        ...     calculate_snr(audio)
        ... except Exception as e:
        ...     raise QualityAnalysisError(
        ...         "SNR calculation failed",
        ...         analysis_type='snr',
        ...         original_error=e
        ...     )
    """
    
    def __init__(
        self,
        message: str,
        analysis_type: str = None,
        original_error: Exception = None
    ):
        """
        Initialize QualityAnalysisError.
        
        Args:
            message: Error message
            analysis_type: Type of analysis that failed (optional)
            original_error: Original exception that caused the failure (optional)
        """
        super().__init__(message)
        self.analysis_type = analysis_type
        self.original_error = original_error
    
    def __str__(self):
        """Return string representation with analysis type if available."""
        if self.analysis_type:
            return f"{self.analysis_type}: {super().__str__()}"
        return super().__str__()


class AudioProcessingError(AudioQualityError):
    """
    Raised when audio processing fails.
    
    This exception is raised when:
    - High-pass filter application fails
    - Noise gate application fails
    - Any other audio processing operation fails
    
    Attributes:
        message: Error message describing the processing failure
        processing_type: Type of processing that failed (e.g., 'high_pass', 'noise_gate')
        original_error: Original exception that caused the failure (if any)
    
    Examples:
        >>> raise AudioProcessingError("High-pass filter failed", processing_type='high_pass')
    """
    
    def __init__(
        self,
        message: str,
        processing_type: str = None,
        original_error: Exception = None
    ):
        """
        Initialize AudioProcessingError.
        
        Args:
            message: Error message
            processing_type: Type of processing that failed (optional)
            original_error: Original exception that caused the failure (optional)
        """
        super().__init__(message)
        self.processing_type = processing_type
        self.original_error = original_error
    
    def __str__(self):
        """Return string representation with processing type if available."""
        if self.processing_type:
            return f"{self.processing_type}: {super().__str__()}"
        return super().__str__()


class ConfigurationError(AudioQualityError):
    """
    Raised when configuration is invalid.
    
    This exception is raised when:
    - Configuration validation fails
    - Required configuration parameters are missing
    - Configuration parameters are out of valid range
    
    Attributes:
        message: Error message describing the configuration issue
        validation_errors: List of validation error messages
    
    Examples:
        >>> raise ConfigurationError(
        ...     "Invalid configuration",
        ...     validation_errors=["SNR threshold must be between 10 and 40 dB"]
        ... )
    """
    
    def __init__(self, message: str, validation_errors: list = None):
        """
        Initialize ConfigurationError.
        
        Args:
            message: Error message
            validation_errors: List of validation error messages (optional)
        """
        super().__init__(message)
        self.validation_errors = validation_errors or []
    
    def __str__(self):
        """Return string representation with validation errors if available."""
        if self.validation_errors:
            errors_str = "; ".join(self.validation_errors)
            return f"{super().__str__()}: {errors_str}"
        return super().__str__()
