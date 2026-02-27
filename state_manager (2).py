"""
State Manager for User Interactions
Updated to support message_id for single message navigation
"""

from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class UserState:
    action: str  # 'adding_language', 'adding_season', 'adding_quality', etc.
    series_id: Optional[str] = None
    lang_id: Optional[str] = None
    season_id: Optional[str] = None
    quality_id: Optional[str] = None
    episode_id: Optional[str] = None  # For episode-level operations
    message_id: Optional[int] = None  # Store the main message ID to update
    first_msg_id: Optional[int] = None  # First message ID in a batch
    last_msg_id: Optional[int] = None  # Last message ID in a batch
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class StateManager:
    """Manages user states for multi-step operations"""
    
    def __init__(self):
        self.states: Dict[int, UserState] = {}
    
    def set_state(self, user_id: int, action: str, **kwargs):
        """Set user state"""
        self.states[user_id] = UserState(action=action, **kwargs)
    
    def get_state(self, user_id: int) -> Optional[UserState]:
        """Get user state"""
        return self.states.get(user_id)
    
    def clear_state(self, user_id: int):
        """Clear user state"""
        if user_id in self.states:
            del self.states[user_id]
    
    def is_state(self, user_id: int, action: str) -> bool:
        """Check if user is in a specific state"""
        state = self.get_state(user_id)
        return state is not None and state.action == action


# Global state manager instance
state_manager = StateManager()
