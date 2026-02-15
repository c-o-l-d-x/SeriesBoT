"""
Force Subscribe Database Handler
Manages users who have joined or requested to join force sub channels
"""
import motor.motor_asyncio
from info import DATABASE_URI, DATABASE_NAME
import logging

logger = logging.getLogger(__name__)


class ForceSubDB:
    """Database handler for force subscribe functionality"""
    
    def __init__(self):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(DATABASE_URI)
        self.db = self._client[DATABASE_NAME]
        self.col = self.db.force_sub_users
        self.settings_col = self.db.force_sub_settings
    
    async def add_user(self, user_id: int, first_name: str, username: str = None, join_date=None):
        """Add a user who has joined or requested to join the force sub channel"""
        try:
            user_data = {
                "_id": int(user_id),
                "user_id": int(user_id),
                "first_name": first_name,
                "username": username,
                "join_date": join_date
            }
            await self.col.insert_one(user_data)
            logger.info(f"Added user {user_id} to force sub database")
            return True
        except Exception as e:
            # User already exists, update their info
            try:
                await self.col.update_one(
                    {"_id": int(user_id)},
                    {"$set": {
                        "first_name": first_name,
                        "username": username
                    }}
                )
                return True
            except Exception as update_error:
                logger.error(f"Error adding/updating user {user_id}: {update_error}")
                return False
    
    async def is_user_authorized(self, user_id: int) -> bool:
        """Check if user has joined or requested to join"""
        try:
            user = await self.col.find_one({"user_id": int(user_id)})
            return user is not None
        except Exception as e:
            logger.error(f"Error checking user authorization: {e}")
            return False
    
    async def get_user(self, user_id: int):
        """Get user details"""
        try:
            return await self.col.find_one({"user_id": int(user_id)})
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    async def delete_user(self, user_id: int):
        """Remove user from force sub database"""
        try:
            await self.col.delete_one({"user_id": int(user_id)})
            return True
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False
    
    async def get_all_users_count(self) -> int:
        """Get total count of authorized users"""
        try:
            return await self.col.count_documents({})
        except Exception as e:
            logger.error(f"Error counting users: {e}")
            return 0
    
    async def delete_all_users(self):
        """Clear all users from force sub database"""
        try:
            result = await self.col.delete_many({})
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting all users: {e}")
            return 0
    
    # Settings Management
    async def get_settings(self):
        """Get force sub settings"""
        try:
            settings = await self.settings_col.find_one({"_id": "force_sub_settings"})
            if not settings:
                # Default settings
                settings = {
                    "_id": "force_sub_settings",
                    "enabled": False,
                    "mode": "request",  # "request" or "normal"
                    "channel_id": None,
                    "channel_username": None,
                    "force_message": None
                }
                await self.settings_col.insert_one(settings)
            return settings
        except Exception as e:
            logger.error(f"Error getting settings: {e}")
            return None
    
    async def update_settings(self, **kwargs):
        """Update force sub settings"""
        try:
            await self.settings_col.update_one(
                {"_id": "force_sub_settings"},
                {"$set": kwargs},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return False
    
    async def enable_force_sub(self, mode: str = "request"):
        """Enable force subscribe with specified mode"""
        return await self.update_settings(enabled=True, mode=mode)
    
    async def disable_force_sub(self):
        """Disable force subscribe"""
        return await self.update_settings(enabled=False)
    
    async def set_channel(self, channel_id: int, username: str = None):
        """Set force sub channel"""
        return await self.update_settings(channel_id=channel_id, channel_username=username)
    
    async def set_force_message(self, message: str):
        """Set custom force sub message"""
        return await self.update_settings(force_message=message)


# Initialize database instance
force_sub_db = ForceSubDB()
