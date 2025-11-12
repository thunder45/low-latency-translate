#!/usr/bin/env python3
"""
Demo script for AudioQualityAnalyzer.

This script demonstrates the usage of AudioQualityAnalyzer with different
types of audio signals (clean, noisy, clipped, silent).
"""

import numpy as np
from audio_quality.analyzers.quality_analyzer import AudioQualityAnalyzer
from audio_quality.models.quality_config import QualityConfig


def generate_clean_audio(sample_rate=16000, duration=1.0):
    """Generate clean sine wave audio."""
    frequency = 440.0  # A4 note
    t = np.linspace(0, duration, int(sample_rate * duration))
    signal = np.sin(2 * np.pi * frequency * t) * 0.3
    return (signal * 32767).astype(np.int16)


def generate_noisy_audio(sample_rate=16000, duration=1.0):
    """Generate noisy audio with low SNR."""
    frequency = 440.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    signal = np.sin(2 * np.pi * frequency * t) * 0.05
    noise = np.random.normal(0, 0.1, len(signal))
    noisy_signal = signal + noise
    return (noisy_signal * 32767).astype(np.int16)


def generate_clipped_audio(sample_rate=16000, duration=1.0):
    """Generate clipped audio."""
    signal = np.random.randn(int(sample_rate * duration))
    signal = signal * 2.0  # Amplify to cause clipping
    signal = np.clip(signal, -1.0, 1.0)
    return (signal * 32767).astype(np.int16)


def generate_silent_audio(sample_rate=16000, duration=1.0):
    """Generate very quiet audio (silence)."""
    signal = np.random.randn(int(sample_rate * duration)) * 0.0001
    return (signal * 32767).astype(np.int16)


def print_metrics(metrics, label):
    """Print quality metrics in a readable format."""
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"{'='*60}")
    print(f"Stream ID: {metrics.stream_id}")
    print(f"Timestamp: {metrics.timestamp:.2f}")
    print(f"\nSNR Metrics:")
    print(f"  Current SNR: {metrics.snr_db:.2f} dB")
    print(f"  Rolling Avg: {metrics.snr_rolling_avg:.2f} dB")
    print(f"\nClipping Metrics:")
    print(f"  Clipping %: {metrics.clipping_percentage:.2f}%")
    print(f"  Clipped Samples: {metrics.clipped_sample_count}")
    print(f"  Is Clipping: {metrics.is_clipping}")
    print(f"\nEcho Metrics:")
    print(f"  Echo Level: {metrics.echo_level_db:.2f} dB")
    print(f"  Echo Delay: {metrics.echo_delay_ms:.2f} ms")
    print(f"  Has Echo: {metrics.has_echo}")
    print(f"\nSilence Metrics:")
    print(f"  Is Silent: {metrics.is_silent}")
    print(f"  Silence Duration: {metrics.silence_duration_s:.2f} s")
    print(f"  Energy Level: {metrics.energy_db:.2f} dB")


def main():
    """Run demo of AudioQualityAnalyzer."""
    print("AudioQualityAnalyzer Demo")
    print("=" * 60)
    
    # Create analyzer with default configuration
    config = QualityConfig(
        snr_threshold_db=20.0,
        clipping_threshold_percent=1.0,
        echo_threshold_db=-15.0,
        silence_threshold_db=-50.0
    )
    analyzer = AudioQualityAnalyzer(config)
    
    sample_rate = 16000
    
    # Test 1: Clean audio
    print("\n\n1. Analyzing CLEAN AUDIO...")
    clean_audio = generate_clean_audio(sample_rate)
    metrics = analyzer.analyze(
        clean_audio,
        sample_rate=sample_rate,
        stream_id='demo-clean'
    )
    print_metrics(metrics, "CLEAN AUDIO RESULTS")
    
    # Test 2: Noisy audio
    print("\n\n2. Analyzing NOISY AUDIO...")
    analyzer.reset()  # Reset state for new stream
    noisy_audio = generate_noisy_audio(sample_rate)
    metrics = analyzer.analyze(
        noisy_audio,
        sample_rate=sample_rate,
        stream_id='demo-noisy'
    )
    print_metrics(metrics, "NOISY AUDIO RESULTS")
    
    # Test 3: Clipped audio
    print("\n\n3. Analyzing CLIPPED AUDIO...")
    analyzer.reset()
    clipped_audio = generate_clipped_audio(sample_rate)
    metrics = analyzer.analyze(
        clipped_audio,
        sample_rate=sample_rate,
        stream_id='demo-clipped'
    )
    print_metrics(metrics, "CLIPPED AUDIO RESULTS")
    
    # Test 4: Silent audio
    print("\n\n4. Analyzing SILENT AUDIO...")
    analyzer.reset()
    silent_audio = generate_silent_audio(sample_rate)
    
    # Analyze at t=0 (not silent yet)
    metrics1 = analyzer.analyze(
        silent_audio,
        sample_rate=sample_rate,
        stream_id='demo-silent',
        timestamp=0.0
    )
    print_metrics(metrics1, "SILENT AUDIO RESULTS (t=0s)")
    
    # Analyze at t=6 (extended silence)
    metrics2 = analyzer.analyze(
        silent_audio,
        sample_rate=sample_rate,
        stream_id='demo-silent',
        timestamp=6.0
    )
    print_metrics(metrics2, "SILENT AUDIO RESULTS (t=6s)")
    
    print("\n\n" + "="*60)
    print("Demo Complete!")
    print("="*60)


if __name__ == '__main__':
    main()
