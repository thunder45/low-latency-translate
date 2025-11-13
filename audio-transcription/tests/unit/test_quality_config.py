"""Unit tests for QualityConfig validation."""

import pytest
from audio_quality.models.quality_config import QualityConfig


class TestQualityConfig:
    """Test suite for QualityConfig validation."""
    
    def test_valid_configuration(self):
        """Test acceptance of valid configuration."""
        config = QualityConfig(
            snr_threshold_db=20.0,
            clipping_threshold_percent=1.0,
            echo_threshold_db=-15.0,
            silence_threshold_db=-50.0
        )
        
        errors = config.validate()
        
        assert len(errors) == 0, f"Valid configuration should have no errors, got: {errors}"
    
    def test_rejection_of_snr_threshold_too_low(self):
        """Test rejection of invalid SNR thresholds (<10 dB)."""
        config = QualityConfig(snr_threshold_db=5.0)
        
        errors = config.validate()
        
        assert len(errors) > 0, "Should reject SNR threshold below 10 dB"
        assert any("SNR threshold" in error and "10" in error for error in errors), \
            f"Error message should mention SNR threshold and 10 dB limit, got: {errors}"
    
    def test_rejection_of_snr_threshold_too_high(self):
        """Test rejection of invalid SNR thresholds (>40 dB)."""
        config = QualityConfig(snr_threshold_db=50.0)
        
        errors = config.validate()
        
        assert len(errors) > 0, "Should reject SNR threshold above 40 dB"
        assert any("SNR threshold" in error and "40" in error for error in errors), \
            f"Error message should mention SNR threshold and 40 dB limit, got: {errors}"
    
    def test_rejection_of_snr_threshold_at_lower_boundary(self):
        """Test SNR threshold at lower boundary (9.9 dB)."""
        config = QualityConfig(snr_threshold_db=9.9)
        
        errors = config.validate()
        
        assert len(errors) > 0, "Should reject SNR threshold just below 10 dB"
    
    def test_acceptance_of_snr_threshold_at_lower_boundary(self):
        """Test SNR threshold at valid lower boundary (10.0 dB)."""
        config = QualityConfig(snr_threshold_db=10.0)
        
        errors = config.validate()
        
        assert len(errors) == 0, f"Should accept SNR threshold at 10 dB, got errors: {errors}"
    
    def test_acceptance_of_snr_threshold_at_upper_boundary(self):
        """Test SNR threshold at valid upper boundary (40.0 dB)."""
        config = QualityConfig(snr_threshold_db=40.0)
        
        errors = config.validate()
        
        assert len(errors) == 0, f"Should accept SNR threshold at 40 dB, got errors: {errors}"
    
    def test_rejection_of_snr_threshold_at_upper_boundary(self):
        """Test SNR threshold at upper boundary (40.1 dB)."""
        config = QualityConfig(snr_threshold_db=40.1)
        
        errors = config.validate()
        
        assert len(errors) > 0, "Should reject SNR threshold just above 40 dB"
    
    def test_rejection_of_clipping_threshold_too_high(self):
        """Test rejection of invalid clipping thresholds (>10%)."""
        config = QualityConfig(clipping_threshold_percent=15.0)
        
        errors = config.validate()
        
        assert len(errors) > 0, "Should reject clipping threshold above 10%"
        assert any("clipping threshold" in error.lower() and "10" in error for error in errors), \
            f"Error message should mention clipping threshold and 10% limit, got: {errors}"
    
    def test_rejection_of_clipping_threshold_too_low(self):
        """Test rejection of invalid clipping thresholds (<0.1%)."""
        config = QualityConfig(clipping_threshold_percent=0.05)
        
        errors = config.validate()
        
        assert len(errors) > 0, "Should reject clipping threshold below 0.1%"
        assert any("clipping threshold" in error.lower() and "0.1" in error for error in errors), \
            f"Error message should mention clipping threshold and 0.1% limit, got: {errors}"
    
    def test_acceptance_of_clipping_threshold_at_lower_boundary(self):
        """Test clipping threshold at valid lower boundary (0.1%)."""
        config = QualityConfig(clipping_threshold_percent=0.1)
        
        errors = config.validate()
        
        assert len(errors) == 0, f"Should accept clipping threshold at 0.1%, got errors: {errors}"
    
    def test_acceptance_of_clipping_threshold_at_upper_boundary(self):
        """Test clipping threshold at valid upper boundary (10.0%)."""
        config = QualityConfig(clipping_threshold_percent=10.0)
        
        errors = config.validate()
        
        assert len(errors) == 0, f"Should accept clipping threshold at 10%, got errors: {errors}"
    
    def test_rejection_of_clipping_threshold_at_upper_boundary(self):
        """Test clipping threshold just above upper boundary (10.1%)."""
        config = QualityConfig(clipping_threshold_percent=10.1)
        
        errors = config.validate()
        
        assert len(errors) > 0, "Should reject clipping threshold just above 10%"
    
    def test_multiple_validation_errors(self):
        """Test that multiple validation errors are reported."""
        config = QualityConfig(
            snr_threshold_db=5.0,  # Too low
            clipping_threshold_percent=15.0  # Too high
        )
        
        errors = config.validate()
        
        assert len(errors) >= 2, f"Should report multiple errors, got: {errors}"
        assert any("SNR" in error for error in errors), "Should include SNR error"
        assert any("clipping" in error.lower() for error in errors), "Should include clipping error"
    
    def test_default_configuration_is_valid(self):
        """Test that default configuration values are valid."""
        config = QualityConfig()
        
        errors = config.validate()
        
        assert len(errors) == 0, f"Default configuration should be valid, got errors: {errors}"
    
    def test_configuration_with_valid_edge_values(self):
        """Test configuration with valid values at edges of ranges."""
        config = QualityConfig(
            snr_threshold_db=10.0,  # Lower boundary
            clipping_threshold_percent=10.0,  # Upper boundary
            echo_threshold_db=-15.0,
            silence_threshold_db=-50.0
        )
        
        errors = config.validate()
        
        assert len(errors) == 0, f"Configuration with edge values should be valid, got errors: {errors}"
    
    def test_configuration_with_typical_values(self):
        """Test configuration with typical production values."""
        config = QualityConfig(
            snr_threshold_db=20.0,
            clipping_threshold_percent=1.0,
            echo_threshold_db=-15.0,
            silence_threshold_db=-50.0,
            silence_duration_threshold_s=5.0
        )
        
        errors = config.validate()
        
        assert len(errors) == 0, f"Typical configuration should be valid, got errors: {errors}"
    
    def test_configuration_maintains_previous_valid_settings_on_error(self):
        """Test that invalid configuration parameters are rejected and previous settings maintained."""
        # Create valid config
        valid_config = QualityConfig(snr_threshold_db=20.0, clipping_threshold_percent=1.0)
        assert len(valid_config.validate()) == 0, "Initial config should be valid"
        
        # Attempt to create invalid config
        invalid_config = QualityConfig(snr_threshold_db=5.0, clipping_threshold_percent=15.0)
        errors = invalid_config.validate()
        
        # Invalid config should report errors
        assert len(errors) > 0, "Invalid config should have errors"
        
        # Original valid config should still be valid
        assert len(valid_config.validate()) == 0, "Original valid config should remain valid"
