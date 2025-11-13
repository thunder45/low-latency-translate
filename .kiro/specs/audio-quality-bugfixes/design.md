# Bug Fix Design Document

## Overview

This document provides detailed design solutions for the six critical bugs discovered in the audio quality validation system. Each bug has been analyzed through test failures, and specific algorithmic fixes are proposed.

## Bug 1: SNR Calculator Algorithm

### Problem Analysis

The current SNR calculation returns incorrect values:
- Clean signals: 35.79 dB (expected >40 dB)
- Noisy signals: 26.25 dB (expected 0-20 dB)
- Very noisy signals: 30.89 dB (expected <10 dB)

**Root Cause**: The noise floor estimation is flawed. The algorithm uses a fixed threshold (0.01 = -40 dB) to identify "noise frames", but this doesn't properly separate signal from noise.

### Solution Design

Implement a proper noise floor estimation using signal statistics:

```python
def calculate_snr(self, audio_chunk: np.ndarray) -> float:
    """
    Calculates SNR using improved noise floor estimation.
    
    Algorithm:
    1. Calculate overall RMS of signal
    2. Estimate noise floor from lowest-energy frames (bottom 10%)
    3. Calculate signal power from frames above noise floor
    4. SNR = 10 * log10(signal_power / noise_power)
    """
    # Normalize to [-1, 1] if int16
    if audio_chunk.dtype == np.int16:
        audio_normalized = audio_chunk.astype(np.float64) / 32768.0
    else:
        audio_normalized = audio_chunk.astype(np.float64)
    
    # Calculate frame-wise RMS (100ms frames)
    frame_size = 1600  # 100ms at 16kHz
    num_frames = len(audio_normalized) // frame_size
    
    if num_frames < 2:
        # Too short, use simple RMS
        rms = np.sqrt(np.mean(audio_normalized ** 2))
        return 20 * np.log10(rms / 1e-10) if rms > 0 else 0.0
    
    frame_rms = []
    for i in range(num_frames):
        frame = audio_normalized[i * frame_size:(i + 1) * frame_size]
        frame_rms.append(np.sqrt(np.mean(frame ** 2)))
    
    frame_rms = np.array(frame_rms)
    
    # Estimate noise floor from lowest 10% of frames
    noise_percentile = 10
    noise_threshold = np.percentile(frame_rms, noise_percentile)
    
    # Separate noise and signal frames
    noise_frames = frame_rms[frame_rms <= noise_threshold]
    signal_frames = frame_rms[frame_rms > noise_threshold]
    
    if len(noise_frames) == 0 or len(signal_frames) == 0:
        # Fallback to simple calculation
        rms = np.sqrt(np.mean(audio_normalized ** 2))
        return 20 * np.log10(rms / 1e-10) if rms > 0 else 0.0
    
    # Calculate noise and signal power
    noise_power = np.mean(noise_frames ** 2)
    signal_power = np.mean(signal_frames ** 2)
    
    # Avoid division by zero
    if noise_power < 1e-10:
        noise_power = 1e-10
    
    # Calculate SNR in dB
    snr_db = 10 * np.log10(signal_power / noise_power)
    
    # Update rolling average
    self.signal_history.append(snr_db)
    
    return float(snr_db)
```

## Bug 2: Echo Detector False Positives and Delay Measurement

### Problem Analysis

The echo detector has two critical issues:
1. **False positives**: Detects echo in clean signals (has_echo=True when should be False)
2. **Wrong delay**: Always reports ~11.38ms regardless of actual echo delay

**Root Cause**: 
- The autocorrelation peak finding is incorrect
- The delay calculation doesn't account for sample rate properly
- The threshold for "avoiding false positives" (0.01) is too low

### Solution Design

Fix the autocorrelation algorithm and peak detection:

```python
def detect_echo(self, audio_chunk: np.ndarray, sample_rate: int) -> EchoResult:
    """
    Detects echo using improved autocorrelation.
    
    Algorithm:
    1. Normalize audio to [-1, 1]
    2. Compute autocorrelation
    3. Find peaks in delay range with proper threshold
    4. Calculate echo level relative to primary signal
    """
    # Normalize to [-1, 1] if int16
    if audio_chunk.dtype == np.int16:
        audio_normalized = audio_chunk.astype(np.float64) / 32768.0
    else:
        audio_normalized = audio_chunk.astype(np.float64)
    
    # Convert delay range to samples
    min_delay = int(self.min_delay_ms * sample_rate / 1000)
    max_delay = int(self.max_delay_ms * sample_rate / 1000)
    
    # Ensure we have enough samples
    if len(audio_normalized) < max_delay:
        return EchoResult(
            echo_level_db=-100.0,
            delay_ms=0.0,
            has_echo=False
        )
    
    # Compute autocorrelation using FFT (faster)
    from scipy import signal as scipy_signal
    autocorr = scipy_signal.correlate(audio_normalized, audio_normalized, mode='full')
    autocorr = autocorr[len(autocorr)//2:]  # Keep positive lags only
    
    # Normalize by zero-lag value
    if autocorr[0] > 0:
        autocorr = autocorr / autocorr[0]
    else:
        return EchoResult(echo_level_db=-100.0, delay_ms=0.0, has_echo=False)
    
    # Search for peaks in delay range
    search_range = autocorr[min_delay:min(max_delay, len(autocorr))]
    
    if len(search_range) == 0:
        return EchoResult(echo_level_db=-100.0, delay_ms=0.0, has_echo=False)
    
    # Find the maximum peak in the search range
    # Use a higher threshold to avoid false positives (0.3 instead of 0.01)
    peak_idx = np.argmax(search_range)
    peak_value = search_range[peak_idx]
    
    # Check if peak is significant (above 0.3 correlation)
    if peak_value < 0.3:
        return EchoResult(
            echo_level_db=-100.0,
            delay_ms=0.0,
            has_echo=False
        )
    
    # Calculate actual delay in samples and milliseconds
    actual_delay_samples = min_delay + peak_idx
    delay_ms = (actual_delay_samples * 1000.0) / sample_rate
    
    # Calculate echo level in dB
    echo_db = 20 * np.log10(peak_value) if peak_value > 0 else -100.0
    
    # Check if echo exceeds threshold
    has_echo = echo_db > self.echo_threshold_db
    
    return EchoResult(
        echo_level_db=float(echo_db),
        delay_ms=float(delay_ms),
        has_echo=bool(has_echo)
    )
```

## Bug 3: Silence Detector State Management

### Problem Analysis

The silence detector doesn't accumulate duration across calls:
- `duration_s` always returns 0.0 instead of accumulating
- `is_silent` is always False even after 6 seconds of silence

**Root Cause**: The `silence_start_time` is not being properly initialized or maintained across calls. The detector is likely resetting state on each call.

### Solution Design

Fix state management to properly track silence duration:

```python
class SilenceDetector:
    """Detects extended silence periods with proper state management."""
    
    def __init__(self, silence_threshold_db: float = -50.0, duration_threshold_s: float = 5.0):
        self.silence_threshold_db = silence_threshold_db
        self.duration_threshold_s = duration_threshold_s
        self.silence_start_time = None  # Track when silence started
        self.last_timestamp = None  # Track last call timestamp
        
    def detect_silence(self, audio_chunk: np.ndarray, timestamp: float) -> SilenceResult:
        """
        Detects extended silence with proper state tracking.
        
        Key fix: Properly maintain silence_start_time across calls.
        """
        # Normalize to [-1, 1] if int16
        if audio_chunk.dtype == np.int16:
            audio_normalized = audio_chunk.astype(np.float64) / 32768.0
        else:
            audio_normalized = audio_chunk.astype(np.float64)
        
        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_normalized ** 2))
        energy_db = 20 * np.log10(rms) if rms > 1e-10 else -100.0
        
        # Check if current chunk is silent
        is_chunk_silent = energy_db < self.silence_threshold_db
        
        if is_chunk_silent:
            # Silent chunk
            if self.silence_start_time is None:
                # Start tracking silence
                self.silence_start_time = timestamp
            
            # Calculate duration
            silence_duration = timestamp - self.silence_start_time
        else:
            # Not silent - reset tracking
            self.silence_start_time = None
            silence_duration = 0.0
        
        # Update last timestamp
        self.last_timestamp = timestamp
        
        # Determine if silence exceeds threshold
        is_silent = silence_duration > self.duration_threshold_s
        
        return SilenceResult(
            is_silent=bool(is_silent),
            duration_s=float(silence_duration),
            energy_db=float(energy_db)
        )
    
    def reset(self):
        """Reset detector state."""
        self.silence_start_time = None
        self.last_timestamp = None
```

## Bug 4: Clipping Detector Threshold Logic

### Problem Analysis

The clipping detector doesn't count samples at threshold:
- Expected 100 clipped samples, got 0
- Samples at threshold (32112) not being counted

**Root Cause**: The threshold calculation or comparison logic is incorrect. The detector may be using the wrong comparison operator or calculating the threshold incorrectly.

### Solution Design

Fix threshold calculation and comparison:

```python
def detect_clipping(self, audio_chunk: np.ndarray, bit_depth: int = 16) -> ClippingResult:
    """
    Detects clipping with corrected threshold logic.
    
    Key fixes:
    1. Proper threshold calculation
    2. Correct comparison operator (>=)
    3. Handle empty arrays gracefully
    """
    # Handle empty array
    if len(audio_chunk) == 0:
        return ClippingResult(
            percentage=0.0,
            clipped_count=0,
            is_clipping=False,
            timestamp=None
        )
    
    # Calculate clipping threshold
    # For 16-bit PCM: max = 32767, threshold at 98% = 32112
    max_amplitude = 2 ** (bit_depth - 1) - 1
    threshold = max_amplitude * (self.threshold_percent / 100.0)
    
    # Count clipped samples (samples >= threshold)
    # Use absolute value to catch both positive and negative clipping
    clipped_samples = np.sum(np.abs(audio_chunk) >= threshold)
    
    # Calculate percentage
    total_samples = len(audio_chunk)
    clipping_percentage = (clipped_samples / total_samples) * 100.0
    
    # Check if exceeds threshold (default 1%)
    is_clipping = clipping_percentage > 1.0
    
    return ClippingResult(
        percentage=float(clipping_percentage),
        clipped_count=int(clipped_samples),
        is_clipping=bool(is_clipping),
        timestamp=None
    )
```

## Bug 5: Metrics Emitter Implementation

### Problem Analysis

The metrics emitter's `emit_metrics()` method doesn't actually call CloudWatch:
- `mock_cloudwatch_client.put_metric_data.called` is False

**Root Cause**: The implementation is likely incomplete or has a logic error preventing the CloudWatch call.

### Solution Design

Ensure CloudWatch calls are made:

```python
def emit_metrics(self, stream_id: str, metrics: QualityMetrics):
    """
    Emits quality metrics to CloudWatch.
    
    Key fix: Ensure put_metric_data is actually called.
    """
    try:
        metric_data = [
            {
                'MetricName': 'SNR',
                'Value': float(metrics.snr_db),
                'Unit': 'None',
                'Dimensions': [{'Name': 'StreamId', 'Value': stream_id}],
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'ClippingPercentage',
                'Value': float(metrics.clipping_percentage),
                'Unit': 'Percent',
                'Dimensions': [{'Name': 'StreamId', 'Value': stream_id}],
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'EchoLevel',
                'Value': float(metrics.echo_level_db),
                'Unit': 'None',
                'Dimensions': [{'Name': 'StreamId', 'Value': stream_id}],
                'Timestamp': datetime.utcnow()
            }
        ]
        
        # Actually call CloudWatch
        self.cloudwatch.put_metric_data(
            Namespace='AudioQuality',
            MetricData=metric_data
        )
        
    except Exception as e:
        logger.error(f"Failed to emit metrics: {e}")
        # Don't raise - graceful degradation
```

## Bug 6: Speaker Notifier WebSocket Integration

### Problem Analysis

The speaker notifier doesn't send messages:
- `mock_websocket_manager.sent_messages` is empty
- `send_message()` is not being called

**Root Cause**: The implementation may have a logic error or the WebSocket manager integration is incomplete.

### Solution Design

Ensure WebSocket messages are sent:

```python
def notify_speaker(self, connection_id: str, issue_type: str, details: dict):
    """
    Sends quality warning to speaker via WebSocket.
    
    Key fix: Ensure send_message is actually called.
    """
    # Check rate limit
    key = f"{connection_id}:{issue_type}"
    current_time = time.time()
    last_notification = self.notification_history.get(key, 0)
    
    if current_time - last_notification < self.rate_limit_seconds:
        logger.debug(f"Rate limit: skipping notification for {issue_type}")
        return  # Skip due to rate limit
    
    # Format warning message
    message = self._format_warning(issue_type, details)
    
    # Create notification payload
    notification = {
        'type': 'audio_quality_warning',
        'issue': issue_type,
        'message': message,
        'details': details,
        'timestamp': current_time
    }
    
    try:
        # Actually send via WebSocket
        self.websocket.send_message(connection_id, notification)
        
        # Update notification history AFTER successful send
        self.notification_history[key] = current_time
        
        logger.info(f"Sent {issue_type} notification to {connection_id}")
        
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        # Don't update history if send failed
```

## Bug 7: QualityMetrics Field Name

### Problem Analysis

Integration tests expect `duration_s` but the field is named `silence_duration_s`.

### Solution Design

Add property for backward compatibility:

```python
@dataclass
class QualityMetrics:
    """Audio quality metrics."""
    
    timestamp: float
    stream_id: str
    snr_db: float
    snr_rolling_avg: float
    clipping_percentage: float
    clipped_sample_count: int
    is_clipping: bool
    echo_level_db: float
    echo_delay_ms: float
    has_echo: bool
    is_silent: bool
    silence_duration_s: float
    energy_db: float
    
    @property
    def duration_s(self) -> float:
        """Alias for silence_duration_s for backward compatibility."""
        return self.silence_duration_s
```

## Testing Strategy

Each bug fix should be validated against the existing unit tests:

1. **SNR Calculator**: Run `test_snr_calculator.py` - all 6 tests should pass
2. **Echo Detector**: Run `test_echo_detector.py` - all 11 tests should pass
3. **Silence Detector**: Run `test_silence_detector.py` - all 11 tests should pass
4. **Clipping Detector**: Run `test_clipping_detector.py` - all 10 tests should pass
5. **Metrics Emitter**: Run `test_lambda_audio_quality_integration.py` - CloudWatch tests should pass
6. **Speaker Notifier**: Run `test_speaker_notifier.py` - all 11 tests should pass
7. **Integration**: Run all integration tests - should achieve >80% pass rate

## Implementation Priority

1. **High Priority** (blocking core functionality):
   - Bug 3: Silence Detector (completely broken)
   - Bug 4: Clipping Detector (not detecting anything)
   - Bug 5: Metrics Emitter (no monitoring)

2. **Medium Priority** (incorrect but functional):
   - Bug 1: SNR Calculator (wrong values)
   - Bug 2: Echo Detector (false positives)

3. **Low Priority** (convenience):
   - Bug 6: Speaker Notifier (notifications not sent)
   - Bug 7: QualityMetrics field name (simple alias)
