"""
Auth Manager Module
Handles dynamic authorization user management for SeriesBot
Stores auth users in MongoDB database for persistence across restarts
"""

import logging
from typing import List, Set
from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self):
        self.auth_users: Set[int] = set()
        self._client = AsyncIOMotorClient(DATABASE_URI)
        self.db = self._client[DATABASE_NAME]
        self.auth_collection = self.db.auth_users
        self._initialized = False
    
    async def initialize(self):
        """Load auth users from database on startup"""
        if self._initialized:
            return
        
        try:
            await self.load_auth_users()
            self._initialized = True
            logger.info("✅ Auth Manager initialized successfully")
        except Exception as e:
            logger.error(f"❌ Error initializing Auth Manager: {e}")
            self.auth_users = set()
    
    async def load_auth_users(self):
        """Load auth users from MongoDB database"""
        try:
            # Get all auth users from database
            cursor = self.auth_collection.find({})
            auth_list = await cursor.to_list(length=None)
            
            self.auth_users = set(doc['user_id'] for doc in auth_list)
            
            logger.info(f"✅ Loaded {len(self.auth_users)} auth users from database")
            if self.auth_users:
                logger.info(f"📋 Auth users: {list(self.auth_users)}")
        except Exception as e:
            logger.error(f"❌ Error loading auth users from database: {e}")
            self.auth_users = set()
    
    async def save_auth_user(self, user_id: int):
        """Save a single auth user to database"""
        try:
            await self.auth_collection.update_one(
                {'user_id': int(user_id)},
                {'$set': {'user_id': int(user_id)}},
                upsert=True
            )
            logger.info(f"💾 Saved auth user {user_id} to database")
        except Exception as e:
            logger.error(f"❌ Error saving auth user {user_id} to database: {e}")
    
    async def delete_auth_user(self, user_id: int):
        """Delete a single auth user from database"""
        try:
            await self.auth_collection.delete_one({'user_id': int(user_id)})
            logger.info(f"🗑️ Deleted auth user {user_id} from database")
        except Exception as e:
            logger.error(f"❌ Error deleting auth user {user_id} from database: {e}")
    
    async def add_auth_user(self, user_id: int) -> bool:
        """Add a user to auth users list"""
        if user_id not in self.auth_users:
            self.auth_users.add(user_id)
            await self.save_auth_user(user_id)
            logger.info(f"✅ Added auth user: {user_id}")
            logger.info(f"📋 Current auth users: {list(self.auth_users)}")
            return True
        logger.info(f"ℹ️ User {user_id} already in auth users")
        return False
    
    async def remove_auth_user(self, user_id: int) -> bool:
        """Remove a user from auth users list"""
        if user_id in self.auth_users:
            self.auth_users.remove(user_id)
            await self.delete_auth_user(user_id)
            logger.info(f"✅ Removed auth user: {user_id}")
            logger.info(f"📋 Current auth users: {list(self.auth_users)}")
            return True
        logger.info(f"ℹ️ User {user_id} not in auth users")
        return False
    
    def is_auth_user(self, user_id: int) -> bool:
        """Check if user is in auth users list"""
        return user_id in self.auth_users
    
    def get_all_auth_users(self) -> List[int]:
        """Get all auth users"""
        return list(self.auth_users)
    
    def get_count(self) -> int:
        """Get total count of auth users"""
        return len(self.auth_users)

# Initialize global auth manager instance
auth_manager = AuthManager()
