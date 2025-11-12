"""
Demo script for QualityMetricsEmitter.

Demonstrates how to use the QualityMetricsEmitter to publish
audio quality metrics to CloudWatch and events to EventBridge.
"""

import time
import numpy as np
from unittest.mock import Mock

from audio_quality.analyzers.quality_analyzer import AudioQualityAnalyzer
from audio_quality.models.quality_config import QualityConfig
from audio_quality.notifiers.metrics_emitter import QualityMetricsEmitter


def main():
    """Demonstrates QualityMetricsEmitter usage."""
    
    print('=== QualityMetricsEmitter Demo ===\n')
    
    # Create mock AWS clients (in production, use real boto3 clients)
    mock_cloudwatch = Mock()
    mock_eventbridge = Mock()
    
    # Initialize metrics emitter
    emitter = QualityMetricsEmitter(
        cloudwatch_client=mock_cloudwatch,
        eventbridge_client=mock_eventbridge,
        batch_size=20,
        flush_interval_s=5.0
    )
    
    print('1. Initialized QualityMetricsEmitter')
    print(f'   - Batch size: {emitter.batch_size}')
    print(f'   - Flush interval: {emitter.flush_interval_s}s\n')
    
    # Initialize quality analyzer
    config = QualityConfig(
        snr_threshold_db=20.0,
        clipping_threshold_percent=1.0,
        echo_threshold_db=-15.0
    )
    analyzer = AudioQualityAnalyzer(config)
    
    print('2. Initialized AudioQualityAnalyzer\n')
    
    # Simulate analyzing audio from multiple streams
    stream_ids = ['stream-001', 'stream-002', 'stream-003']
    
    for stream_id in stream_ids:
        print(f'3. Processing {stream_id}...')
        
        # Generate sample audio
        sample_rate = 16000
        duration = 1.0
        audio_chunk = np.random.randn(int(sample_rate * duration)) * 0.1
        
        # Analyze audio quality
        metrics = analyzer.analyze(
            audio_chunk,
            sample_rate,
            stream_id=stream_id,
            timestamp=time.time()
        )
        
        print(f'   - SNR: {metrics.snr_db:.1f} dB')
        print(f'   - Clipping: {metrics.clipping_percentage:.2f}%')
        print(f'   - Echo: {metrics.echo_level_db:.1f} dB')
        print(f'   - Silent: {metrics.is_silent}')
        
        # Emit metrics to CloudWatch
        emitter.emit_metrics(stream_id, metrics)
        print(f'   - Metrics added to buffer (buffer size: {len(emitter.metric_buffer)})')
        
        # Check for quality issues and emit events
        if metrics.snr_db < config.snr_threshold_db:
            print(f'   ⚠️  Low SNR detected!')
            emitter.emit_quality_event(
                stream_id=stream_id,
                event_type='snr_low',
                details={
                    'severity': 'warning',
                    'metrics': {
                        'snr': metrics.snr_db,
                        'threshold': config.snr_threshold_db
                    },
                    'message': f'SNR {metrics.snr_db:.1f} dB below threshold {config.snr_threshold_db} dB'
                }
            )
        
        if metrics.is_clipping:
            print(f'   ⚠️  Clipping detected!')
            emitter.emit_quality_event(
                stream_id=stream_id,
                event_type='clipping',
                details={
                    'severity': 'error',
                    'metrics': {
                        'percentage': metrics.clipping_percentage,
                        'threshold': config.clipping_threshold_percent
                    },
                    'message': f'Clipping {metrics.clipping_percentage:.2f}% exceeds threshold'
                }
            )
        
        print()
    
    # Manually flush remaining metrics
    print('4. Flushing remaining metrics...')
    emitter.flush()
    print(f'   - Buffer cleared (size: {len(emitter.metric_buffer)})\n')
    
    # Show API call summary
    print('5. API Call Summary:')
    print(f'   - CloudWatch put_metric_data calls: {mock_cloudwatch.put_metric_data.call_count}')
    print(f'   - EventBridge put_events calls: {mock_eventbridge.put_events.call_count}')
    
    if mock_cloudwatch.put_metric_data.call_count > 0:
        last_call = mock_cloudwatch.put_metric_data.call_args
        metric_count = len(last_call[1]['MetricData'])
        print(f'   - Metrics in last batch: {metric_count}')
    
    print('\n=== Demo Complete ===')
    
    # Demonstrate batching efficiency
    print('\n=== Batching Efficiency Demo ===\n')
    
    # Reset mock
    mock_cloudwatch.reset_mock()
    
    # Create new emitter with small batch size
    emitter2 = QualityMetricsEmitter(
        cloudwatch_client=mock_cloudwatch,
        eventbridge_client=mock_eventbridge,
        batch_size=4,  # Small batch for demo
        flush_interval_s=100.0
    )
    
    print('6. Emitting metrics with batch_size=4...')
    
    # Emit metrics for one stream (4 metrics)
    metrics = analyzer.analyze(
        np.random.randn(16000) * 0.1,
        16000,
        stream_id='demo-stream',
        timestamp=time.time()
    )
    
    print(f'   - Before emit: {mock_cloudwatch.put_metric_data.call_count} API calls')
    emitter2.emit_metrics('demo-stream', metrics)
    print(f'   - After emit: {mock_cloudwatch.put_metric_data.call_count} API calls')
    print(f'   - Auto-flushed when batch size reached!')
    
    print('\n=== Batching Demo Complete ===')


if __name__ == '__main__':
    main()
