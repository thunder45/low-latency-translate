"""
BroadcastState model for session broadcast control.
"""
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class BroadcastState:
    """
    Represents the current broadcast state of a session.
    
    Attributes:
        isActive: Whether broadcasting is active
        isPaused: Whether broadcast is paused
        isMuted: Whether broadcast is muted
        volume: Volume level (0.0-1.0)
        lastStateChange: Unix timestamp of last state change
    """
    isActive: bool = True
    isPaused: bool = False
    isMuted: bool = False
    volume: float = 1.0
    lastStateChange: int = 0
    
    def __post_init__(self):
        """Validate broadcast state values."""
        if not 0.0 <= self.volume <= 1.0:
            raise ValueError(f"Volume must be between 0.0 and 1.0, got {self.volume}")
        
        if self.lastStateChange == 0:
            self.lastStateChange = int(time.time() * 1000)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for DynamoDB storage.
        
        Returns:
            Dictionary representation with Decimal for volume
        """
        from decimal import Decimal
        
        data = asdict(self)
        # Convert volume to Decimal for DynamoDB
        data['volume'] = Decimal(str(self.volume))
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BroadcastState':
        """
        Create BroadcastState from dictionary.
        
        Args:
            data: Dictionary with broadcast state fields
            
        Returns:
            BroadcastState instance
        """
        return cls(
            isActive=data.get('isActive', True),
            isPaused=data.get('isPaused', False),
            isMuted=data.get('isMuted', False),
            volume=float(data.get('volume', 1.0)),
            lastStateChange=int(data.get('lastStateChange', 0))
        )
    
    @classmethod
    def default(cls) -> 'BroadcastState':
        """
        Create default broadcast state.
        
        Returns:
            BroadcastState with default values
        """
        return cls(
            isActive=True,
            isPaused=False,
            isMuted=False,
            volume=1.0,
            lastStateChange=int(time.time() * 1000)
        )
    
    def pause(self) -> 'BroadcastState':
        """
        Create new state with isPaused=True.
        
        Returns:
            New BroadcastState instance
        """
        return BroadcastState(
            isActive=self.isActive,
            isPaused=True,
            isMuted=self.isMuted,
            volume=self.volume,
            lastStateChange=int(time.time() * 1000)
        )
    
    def resume(self) -> 'BroadcastState':
        """
        Create new state with isPaused=False.
        
        Returns:
            New BroadcastState instance
        """
        return BroadcastState(
            isActive=self.isActive,
            isPaused=False,
            isMuted=self.isMuted,
            volume=self.volume,
            lastStateChange=int(time.time() * 1000)
        )
    
    def mute(self) -> 'BroadcastState':
        """
        Create new state with isMuted=True.
        
        Returns:
            New BroadcastState instance
        """
        return BroadcastState(
            isActive=self.isActive,
            isPaused=self.isPaused,
            isMuted=True,
            volume=self.volume,
            lastStateChange=int(time.time() * 1000)
        )
    
    def unmute(self) -> 'BroadcastState':
        """
        Create new state with isMuted=False.
        
        Returns:
            New BroadcastState instance
        """
        return BroadcastState(
            isActive=self.isActive,
            isPaused=self.isPaused,
            isMuted=False,
            volume=self.volume,
            lastStateChange=int(time.time() * 1000)
        )
    
    def set_volume(self, volume: float) -> 'BroadcastState':
        """
        Create new state with updated volume.
        
        Args:
            volume: New volume level (0.0-1.0)
            
        Returns:
            New BroadcastState instance
            
        Raises:
            ValueError: If volume is out of range
        """
        if not 0.0 <= volume <= 1.0:
            raise ValueError(f"Volume must be between 0.0 and 1.0, got {volume}")
        
        return BroadcastState(
            isActive=self.isActive,
            isPaused=self.isPaused,
            isMuted=self.isMuted,
            volume=volume,
            lastStateChange=int(time.time() * 1000)
        )
    
    def is_broadcasting(self) -> bool:
        """
        Check if currently broadcasting (active, not paused, not muted).
        
        Returns:
            True if broadcasting, False otherwise
        """
        return self.isActive and not self.isPaused and not self.isMuted
