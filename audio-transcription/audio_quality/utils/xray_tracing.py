"""
AWS X-Ray tracing utilities for audio quality validation.

Provides decorators and context managers for distributed tracing
of audio quality analysis operations.
"""

import functools
from typing import Callable, Any, Optional

try:
    from aws_xray_sdk.core import xray_recorder
    XRAY_AVAILABLE = True
except ImportError:
    XRAY_AVAILABLE = False
    # Create no-op decorator when X-Ray SDK not available
    class NoOpRecorder:
        """No-op recorder when X-Ray SDK is not available."""
        
        def capture(self, name: str):
            """No-op capture decorator."""
            def decorator(func: Callable) -> Callable:
                return func
            return decorator
        
        def begin_subsegment(self, name: str):
            """No-op context manager."""
            return NoOpContext()
        
        def end_subsegment(self):
            """No-op end subsegment."""
            pass
    
    class NoOpContext:
        """No-op context manager."""
        def __enter__(self):
            return self
        
        def __exit__(self, *args):
            pass
    
    xray_recorder = NoOpRecorder()


def trace_audio_analysis(func: Callable) -> Callable:
    """
    Decorator to trace audio quality analysis functions with X-Ray.
    
    Creates a subsegment for the decorated function and captures
    execution time and any exceptions.
    
    Args:
        func: Function to trace
        
    Returns:
        Wrapped function with X-Ray tracing
        
    Examples:
        >>> @trace_audio_analysis
        ... def analyze_audio(audio_chunk):
        ...     return calculate_metrics(audio_chunk)
    """
    if not XRAY_AVAILABLE:
        # Return unwrapped function if X-Ray not available
        return func
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        segment_name = f'audio_quality.{func.__name__}'
        
        try:
            subsegment = xray_recorder.begin_subsegment(segment_name)
            if subsegment is None:
                # No parent segment, run without tracing
                return func(*args, **kwargs)
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                # X-Ray will automatically capture the exception
                raise
            finally:
                xray_recorder.end_subsegment()
        except Exception:
            # If X-Ray tracing fails, run function without tracing
            return func(*args, **kwargs)
    
    return wrapper


def trace_detector(detector_name: str):
    """
    Decorator factory to trace specific detector operations.
    
    Creates a subsegment with the detector name for better
    visibility in X-Ray traces.
    
    Args:
        detector_name: Name of the detector (e.g., 'snr', 'clipping', 'echo')
        
    Returns:
        Decorator function
        
    Examples:
        >>> @trace_detector('snr')
        ... def calculate_snr(audio_chunk):
        ...     return compute_snr(audio_chunk)
    """
    def decorator(func: Callable) -> Callable:
        if not XRAY_AVAILABLE:
            return func
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            segment_name = f'detector.{detector_name}'
            
            with xray_recorder.begin_subsegment(segment_name):
                try:
                    result = func(*args, **kwargs)
                    
                    # Add metadata if result has metrics
                    if hasattr(result, '__dict__'):
                        xray_recorder.current_subsegment().put_metadata(
                            'result',
                            result.__dict__,
                            'audio_quality'
                        )
                    
                    return result
                except Exception as e:
                    raise
        
        return wrapper
    return decorator


class XRayContext:
    """
    Context manager for X-Ray subsegments.
    
    Provides a convenient way to create subsegments for code blocks
    without using decorators.
    
    Examples:
        >>> with XRayContext('process_audio'):
        ...     audio_data = load_audio()
        ...     metrics = analyze(audio_data)
    """
    
    def __init__(self, name: str, metadata: Optional[dict] = None):
        """
        Initialize X-Ray context.
        
        Args:
            name: Subsegment name
            metadata: Optional metadata to attach to subsegment
        """
        self.name = name
        self.metadata = metadata or {}
        self.subsegment = None
    
    def __enter__(self):
        """Enter context and begin subsegment."""
        if XRAY_AVAILABLE:
            try:
                self.subsegment = xray_recorder.begin_subsegment(self.name)
                
                # Add metadata if subsegment was created
                if self.subsegment and self.metadata:
                    for key, value in self.metadata.items():
                        xray_recorder.current_subsegment().put_metadata(
                            key,
                            value,
                            'audio_quality'
                        )
            except Exception:
                # If X-Ray tracing fails, continue without tracing
                self.subsegment = None
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and end subsegment."""
        if XRAY_AVAILABLE and self.subsegment:
            try:
                xray_recorder.end_subsegment()
            except Exception:
                # If ending subsegment fails, continue without error
                pass
        
        # Don't suppress exceptions
        return False
    
    def add_annotation(self, key: str, value: Any):
        """
        Add annotation to current subsegment.
        
        Annotations are indexed and can be used for filtering traces.
        
        Args:
            key: Annotation key
            value: Annotation value (must be string, number, or boolean)
        """
        if XRAY_AVAILABLE and self.subsegment:
            xray_recorder.current_subsegment().put_annotation(key, value)
    
    def add_metadata(self, key: str, value: Any):
        """
        Add metadata to current subsegment.
        
        Metadata is not indexed but can contain complex objects.
        
        Args:
            key: Metadata key
            value: Metadata value (any JSON-serializable object)
        """
        if XRAY_AVAILABLE and self.subsegment:
            xray_recorder.current_subsegment().put_metadata(
                key,
                value,
                'audio_quality'
            )


def is_xray_available() -> bool:
    """
    Check if X-Ray SDK is available.
    
    Returns:
        True if X-Ray SDK is installed and available
    """
    return XRAY_AVAILABLE
