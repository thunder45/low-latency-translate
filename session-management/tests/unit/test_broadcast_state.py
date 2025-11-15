"""
Unit tests for BroadcastState model.
"""
import pytest
import time
from shared.models.broadcast_state import BroadcastState


class TestBroadcastState:
    """Test suite for BroadcastState model."""
    
    def test_default_state(self):
        """Test default broadcast state creation."""
        state = BroadcastState.default()
        
        assert state.isActive is True
        assert state.isPaused is False
        assert state.isMuted is False
        assert state.volume == 1.0
        assert state.lastStateChange > 0
    
    def test_custom_state(self):
        """Test custom broadcast state creation."""
        timestamp = int(time.time() * 1000)
        state = BroadcastState(
            isActive=True,
            isPaused=True,
            isMuted=False,
            volume=0.5,
            lastStateChange=timestamp
        )
        
        assert state.isActive is True
        assert state.isPaused is True
        assert state.isMuted is False
        assert state.volume == 0.5
        assert state.lastStateChange == timestamp
    
    def test_volume_validation(self):
        """Test volume validation."""
        # Valid volumes
        BroadcastState(volume=0.0)
        BroadcastState(volume=0.5)
        BroadcastState(volume=1.0)
        
        # Invalid volumes
        with pytest.raises(ValueError, match="Volume must be between 0.0 and 1.0"):
            BroadcastState(volume=-0.1)
        
        with pytest.raises(ValueError, match="Volume must be between 0.0 and 1.0"):
            BroadcastState(volume=1.1)
    
    def test_pause(self):
        """Test pause operation."""
        state = BroadcastState.default()
        paused_state = state.pause()
        
        assert paused_state.isPaused is True
        assert paused_state.isActive == state.isActive
        assert paused_state.isMuted == state.isMuted
        assert paused_state.volume == state.volume
        assert paused_state.lastStateChange >= state.lastStateChange
    
    def test_resume(self):
        """Test resume operation."""
        state = BroadcastState(isPaused=True)
        resumed_state = state.resume()
        
        assert resumed_state.isPaused is False
        assert resumed_state.isActive == state.isActive
        assert resumed_state.isMuted == state.isMuted
        assert resumed_state.volume == state.volume
    
    def test_mute(self):
        """Test mute operation."""
        state = BroadcastState.default()
        muted_state = state.mute()
        
        assert muted_state.isMuted is True
        assert muted_state.isActive == state.isActive
        assert muted_state.isPaused == state.isPaused
        assert muted_state.volume == state.volume
    
    def test_unmute(self):
        """Test unmute operation."""
        state = BroadcastState(isMuted=True)
        unmuted_state = state.unmute()
        
        assert unmuted_state.isMuted is False
        assert unmuted_state.isActive == state.isActive
        assert unmuted_state.isPaused == state.isPaused
        assert unmuted_state.volume == state.volume
    
    def test_set_volume(self):
        """Test set volume operation."""
        state = BroadcastState.default()
        new_state = state.set_volume(0.7)
        
        assert new_state.volume == 0.7
        assert new_state.isActive == state.isActive
        assert new_state.isPaused == state.isPaused
        assert new_state.isMuted == state.isMuted
    
    def test_set_volume_validation(self):
        """Test set volume validation."""
        state = BroadcastState.default()
        
        with pytest.raises(ValueError, match="Volume must be between 0.0 and 1.0"):
            state.set_volume(-0.1)
        
        with pytest.raises(ValueError, match="Volume must be between 0.0 and 1.0"):
            state.set_volume(1.5)
    
    def test_is_broadcasting(self):
        """Test is_broadcasting check."""
        # Broadcasting: active, not paused, not muted
        state = BroadcastState(isActive=True, isPaused=False, isMuted=False)
        assert state.is_broadcasting() is True
        
        # Not broadcasting: paused
        state = BroadcastState(isActive=True, isPaused=True, isMuted=False)
        assert state.is_broadcasting() is False
        
        # Not broadcasting: muted
        state = BroadcastState(isActive=True, isPaused=False, isMuted=True)
        assert state.is_broadcasting() is False
        
        # Not broadcasting: inactive
        state = BroadcastState(isActive=False, isPaused=False, isMuted=False)
        assert state.is_broadcasting() is False
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        timestamp = int(time.time() * 1000)
        state = BroadcastState(
            isActive=True,
            isPaused=True,
            isMuted=False,
            volume=0.8,
            lastStateChange=timestamp
        )
        
        data = state.to_dict()
        
        assert data['isActive'] is True
        assert data['isPaused'] is True
        assert data['isMuted'] is False
        assert float(data['volume']) == 0.8  # Volume is Decimal in DynamoDB format
        assert data['lastStateChange'] == timestamp
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        timestamp = int(time.time() * 1000)
        data = {
            'isActive': True,
            'isPaused': True,
            'isMuted': False,
            'volume': 0.6,
            'lastStateChange': timestamp
        }
        
        state = BroadcastState.from_dict(data)
        
        assert state.isActive is True
        assert state.isPaused is True
        assert state.isMuted is False
        assert state.volume == 0.6
        assert state.lastStateChange == timestamp
    
    def test_from_dict_with_defaults(self):
        """Test creation from dictionary with missing fields."""
        data = {}
        state = BroadcastState.from_dict(data)
        
        assert state.isActive is True
        assert state.isPaused is False
        assert state.isMuted is False
        assert state.volume == 1.0
        # lastStateChange is auto-set in __post_init__ if 0
        assert state.lastStateChange > 0
    
    def test_round_trip_serialization(self):
        """Test round-trip serialization."""
        original = BroadcastState(
            isActive=True,
            isPaused=True,
            isMuted=False,
            volume=0.75,
            lastStateChange=int(time.time() * 1000)
        )
        
        data = original.to_dict()
        restored = BroadcastState.from_dict(data)
        
        assert restored.isActive == original.isActive
        assert restored.isPaused == original.isPaused
        assert restored.isMuted == original.isMuted
        assert restored.volume == original.volume
        assert restored.lastStateChange == original.lastStateChange
