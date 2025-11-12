"""
Demo script for AudioProcessor.

This script demonstrates how to use the AudioProcessor class to apply
optional audio enhancements such as high-pass filtering and noise gating.
"""

import numpy as np
import matplotlib.pyplot as plt
from audio_quality import AudioProcessor, QualityConfig


def generate_noisy_audio(sample_rate: int = 16000, duration: float = 1.0) -> np.ndarray:
    """
    Generates audio with low-frequency noise and background noise.
    
    Args:
        sample_rate: Sample rate in Hz
        duration: Duration in seconds
        
    Returns:
        Audio samples with noise
    """
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Generate speech-like signal (440 Hz fundamental)
    signal = np.sin(2 * np.pi * 440 * t) * 0.3
    
    # Add low-frequency rumble (30 Hz)
    rumble = np.sin(2 * np.pi * 30 * t) * 0.2
    
    # Add background noise
    noise = np.random.normal(0, 0.05, len(t))
    
    # Combine
    noisy_audio = signal + rumble + noise
    
    return noisy_audio


def plot_audio_comparison(
    original: np.ndarray,
    processed: np.ndarray,
    sample_rate: int,
    title: str
):
    """
    Plots original and processed audio for comparison.
    
    Args:
        original: Original audio samples
        processed: Processed audio samples
        sample_rate: Sample rate in Hz
        title: Plot title
    """
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(title)
    
    # Time domain - original
    time = np.arange(len(original)) / sample_rate
    axes[0, 0].plot(time, original)
    axes[0, 0].set_title('Original - Time Domain')
    axes[0, 0].set_xlabel('Time (s)')
    axes[0, 0].set_ylabel('Amplitude')
    axes[0, 0].grid(True)
    
    # Time domain - processed
    axes[0, 1].plot(time, processed)
    axes[0, 1].set_title('Processed - Time Domain')
    axes[0, 1].set_xlabel('Time (s)')
    axes[0, 1].set_ylabel('Amplitude')
    axes[0, 1].grid(True)
    
    # Frequency domain - original
    fft_original = np.fft.rfft(original)
    freqs = np.fft.rfftfreq(len(original), 1/sample_rate)
    axes[1, 0].plot(freqs, 20 * np.log10(np.abs(fft_original) + 1e-10))
    axes[1, 0].set_title('Original - Frequency Domain')
    axes[1, 0].set_xlabel('Frequency (Hz)')
    axes[1, 0].set_ylabel('Magnitude (dB)')
    axes[1, 0].set_xlim(0, 2000)
    axes[1, 0].grid(True)
    
    # Frequency domain - processed
    fft_processed = np.fft.rfft(processed)
    axes[1, 1].plot(freqs, 20 * np.log10(np.abs(fft_processed) + 1e-10))
    axes[1, 1].set_title('Processed - Frequency Domain')
    axes[1, 1].set_xlabel('Frequency (Hz)')
    axes[1, 1].set_ylabel('Magnitude (dB)')
    axes[1, 1].set_xlim(0, 2000)
    axes[1, 1].grid(True)
    
    plt.tight_layout()
    plt.show()


def demo_high_pass_filter():
    """Demonstrates high-pass filter functionality."""
    print('=== High-Pass Filter Demo ===\n')
    
    # Generate noisy audio
    sample_rate = 16000
    audio = generate_noisy_audio(sample_rate)
    
    # Create processor with high-pass enabled
    config = QualityConfig(enable_high_pass=True, enable_noise_gate=False)
    processor = AudioProcessor(config)
    
    # Process audio
    processed = processor.process(audio, sample_rate)
    
    # Calculate energy in low frequencies (0-100 Hz)
    fft_original = np.fft.rfft(audio)
    fft_processed = np.fft.rfft(processed)
    freqs = np.fft.rfftfreq(len(audio), 1/sample_rate)
    
    low_freq_mask = freqs < 100
    original_low_energy = np.sum(np.abs(fft_original[low_freq_mask]) ** 2)
    processed_low_energy = np.sum(np.abs(fft_processed[low_freq_mask]) ** 2)
    
    reduction_db = 10 * np.log10(processed_low_energy / original_low_energy)
    
    print(f'Sample rate: {sample_rate} Hz')
    print(f'Audio duration: {len(audio) / sample_rate:.2f} seconds')
    print(f'Low-frequency energy reduction: {reduction_db:.1f} dB')
    print(f'High-pass filter cutoff: 80 Hz')
    print()
    
    # Plot comparison
    plot_audio_comparison(audio, processed, sample_rate, 'High-Pass Filter Effect')


def demo_noise_gate():
    """Demonstrates noise gate functionality."""
    print('=== Noise Gate Demo ===\n')
    
    sample_rate = 16000
    
    # Generate audio with quiet and loud sections
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Loud section (0-1s)
    loud_section = np.sin(2 * np.pi * 440 * t[:sample_rate]) * 0.3
    
    # Quiet section (1-2s) - background noise only
    quiet_section = np.random.normal(0, 0.01, sample_rate)
    
    audio = np.concatenate([loud_section, quiet_section])
    
    # Create processor with noise gate enabled
    config = QualityConfig(enable_high_pass=False, enable_noise_gate=True)
    processor = AudioProcessor(config)
    
    # Process audio
    processed = processor.process(audio, sample_rate)
    
    # Calculate RMS for each section
    loud_rms_original = np.sqrt(np.mean(audio[:sample_rate] ** 2))
    quiet_rms_original = np.sqrt(np.mean(audio[sample_rate:] ** 2))
    loud_rms_processed = np.sqrt(np.mean(processed[:sample_rate] ** 2))
    quiet_rms_processed = np.sqrt(np.mean(processed[sample_rate:] ** 2))
    
    print(f'Sample rate: {sample_rate} Hz')
    print(f'Audio duration: {len(audio) / sample_rate:.2f} seconds')
    print()
    print('Loud section (0-1s):')
    print(f'  Original RMS: {20 * np.log10(loud_rms_original):.1f} dB')
    print(f'  Processed RMS: {20 * np.log10(loud_rms_processed):.1f} dB')
    print()
    print('Quiet section (1-2s):')
    print(f'  Original RMS: {20 * np.log10(quiet_rms_original):.1f} dB')
    print(f'  Processed RMS: {20 * np.log10(quiet_rms_processed):.1f} dB')
    print(f'  Attenuation: {20 * np.log10(quiet_rms_processed / quiet_rms_original):.1f} dB')
    print()
    
    # Plot comparison
    plot_audio_comparison(audio, processed, sample_rate, 'Noise Gate Effect')


def demo_combined_processing():
    """Demonstrates combined high-pass filter and noise gate."""
    print('=== Combined Processing Demo ===\n')
    
    # Generate noisy audio
    sample_rate = 16000
    audio = generate_noisy_audio(sample_rate)
    
    # Create processor with both enhancements enabled
    config = QualityConfig(enable_high_pass=True, enable_noise_gate=True)
    processor = AudioProcessor(config)
    
    # Process audio
    processed = processor.process(audio, sample_rate)
    
    # Calculate overall improvement
    original_rms = np.sqrt(np.mean(audio ** 2))
    processed_rms = np.sqrt(np.mean(processed ** 2))
    
    print(f'Sample rate: {sample_rate} Hz')
    print(f'Audio duration: {len(audio) / sample_rate:.2f} seconds')
    print(f'Processing enabled: High-pass filter + Noise gate')
    print()
    print(f'Original RMS: {20 * np.log10(original_rms):.1f} dB')
    print(f'Processed RMS: {20 * np.log10(processed_rms):.1f} dB')
    print()
    
    # Plot comparison
    plot_audio_comparison(audio, processed, sample_rate, 'Combined Processing Effect')


def demo_disabled_processing():
    """Demonstrates that processing can be disabled."""
    print('=== Disabled Processing Demo ===\n')
    
    # Generate noisy audio
    sample_rate = 16000
    audio = generate_noisy_audio(sample_rate)
    
    # Create processor with processing disabled
    config = QualityConfig(enable_high_pass=False, enable_noise_gate=False)
    processor = AudioProcessor(config)
    
    # Process audio (should be unchanged)
    processed = processor.process(audio, sample_rate)
    
    # Verify audio is unchanged
    difference = np.max(np.abs(audio - processed))
    
    print(f'Sample rate: {sample_rate} Hz')
    print(f'Audio duration: {len(audio) / sample_rate:.2f} seconds')
    print(f'Processing enabled: None')
    print()
    print(f'Max difference between original and processed: {difference:.10f}')
    print(f'Audio unchanged: {difference < 1e-10}')
    print()


if __name__ == '__main__':
    print('AudioProcessor Demo\n')
    print('This demo shows how to use AudioProcessor to apply optional')
    print('audio enhancements such as high-pass filtering and noise gating.\n')
    
    # Run demos
    demo_high_pass_filter()
    print('\n' + '='*60 + '\n')
    
    demo_noise_gate()
    print('\n' + '='*60 + '\n')
    
    demo_combined_processing()
    print('\n' + '='*60 + '\n')
    
    demo_disabled_processing()
    
    print('\nDemo complete!')

