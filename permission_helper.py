"""
Permission Helper Module
Provides permission checking functions for SeriesBot
"""

from auth_manager import auth_manager
from info import ADMINS


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMINS


def is_auth_user(user_id: int) -> bool:
    """Check if user is auth user (not admin)"""
    return auth_manager.is_auth_user(user_id)


def is_auth_user_or_admin(user_id: int) -> bool:
    """Check if user is auth user or admin"""
    return is_admin(user_id) or is_auth_user(user_id)


def has_permission(user_id: int, command_level: str) -> bool:
    """
    Check if user has permission for a command
    
    Args:
        user_id: User ID to check
        command_level: 'admin', 'auth', or 'user'
    
    Returns:
        bool: True if user has permission
    """
    if command_level == 'admin':
        return is_admin(user_id)
    elif command_level == 'auth':
        return is_auth_user_or_admin(user_id)
    elif command_level == 'user':
        return True  # All users (add ban check if needed)
    return False
