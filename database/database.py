import motor.motor_asyncio
from info import DATABASE_URI, DATABASE_NAME
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Database:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.groups = self.db.groups  # New collection for groups
        
    def new_user(self, id):
        """Create new user document"""
        return dict(
            _id=int(id),
            join_date=datetime.now(),
            is_blocked=False,
            is_deactivated=False,
            last_active=datetime.now()
        )
               
    async def add_user(self, id):
        """Add new user to database"""
        try:
            user = self.new_user(id)
            await self.col.insert_one(user)
            logger.info(f"New user added: {id}")
            return True
        except Exception as e:
            logger.error(f"Error adding user {id}: {e}")
            return False
    
    async def is_user_exist(self, id):
        """Check if user exists in database"""
        user = await self.col.find_one({'_id': int(id)})
        return bool(user)
    
    async def total_users_count(self):
        """Get total active users count (excluding blocked/deactivated)"""
        count = await self.col.count_documents({
            'is_blocked': {'$ne': True},
            'is_deactivated': {'$ne': True}
        })
        return count
    
    async def get_all_active_users(self):
        """Get all active users for broadcast"""
        return self.col.find({
            'is_blocked': {'$ne': True},
            'is_deactivated': {'$ne': True}
        })
    
    async def get_all_users(self):
        """Get all users (including inactive ones)"""
        return self.col.find({})
    
    async def mark_user_blocked(self, user_id):
        """Mark user as blocked"""
        try:
            await self.col.update_one(
                {'_id': int(user_id)},
                {'$set': {'is_blocked': True}}
            )
            logger.info(f"User {user_id} marked as blocked")
        except Exception as e:
            logger.error(f"Error marking user {user_id} as blocked: {e}")
    
    async def mark_user_deactivated(self, user_id):
        """Mark user as deactivated"""
        try:
            await self.col.update_one(
                {'_id': int(user_id)},
                {'$set': {'is_deactivated': True}}
            )
            logger.info(f"User {user_id} marked as deactivated")
        except Exception as e:
            logger.error(f"Error marking user {user_id} as deactivated: {e}")
    
    async def update_last_active(self, user_id):
        """Update user's last active timestamp"""
        try:
            await self.col.update_one(
                {'_id': int(user_id)},
                {'$set': {
                    'last_active': datetime.now(),
                    'is_blocked': False  # Unmark if user becomes active again
                }}
            )
        except Exception as e:
            logger.error(f"Error updating last active for {user_id}: {e}")
    
    async def delete_user(self, user_id):
        """Permanently delete user from database"""
        try:
            await self.col.delete_one({'_id': int(user_id)})
            logger.info(f"User {user_id} deleted from database")
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
    
    async def cleanup_inactive_users(self):
        """Remove blocked and deactivated users from database"""
        try:
            result = await self.col.delete_many({
                '$or': [
                    {'is_blocked': True},
                    {'is_deactivated': True}
                ]
            })
            logger.info(f"Cleaned up {result.deleted_count} inactive users")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up inactive users: {e}")
            return 0
    
    async def get_user_stats(self):
        """Get detailed user statistics"""
        total = await self.col.count_documents({})
        active = await self.col.count_documents({
            'is_blocked': {'$ne': True},
            'is_deactivated': {'$ne': True}
        })
        blocked = await self.col.count_documents({'is_blocked': True})
        deactivated = await self.col.count_documents({'is_deactivated': True})
        
        return {
            'total': total,
            'active': active,
            'blocked': blocked,
            'deactivated': deactivated
        }
    
    # =================== GROUP TRACKING METHODS ===================
    
    async def add_group(self, chat_id, title="Unknown"):
        """Add a group to database"""
        try:
            await self.groups.update_one(
                {'chat_id': int(chat_id)},
                {
                    '$set': {
                        'chat_id': int(chat_id),
                        'title': title,
                        'joined_at': datetime.now(),
                        'is_active': True,
                        'last_broadcast': None
                    }
                },
                upsert=True
            )
            logger.info(f"Group {chat_id} added/updated in database")
            return True
        except Exception as e:
            logger.error(f"Error adding group {chat_id}: {e}")
            return False
    
    async def remove_group(self, chat_id):
        """Remove a group from database"""
        try:
            await self.groups.delete_one({'chat_id': int(chat_id)})
            logger.info(f"Group {chat_id} removed from database")
            return True
        except Exception as e:
            logger.error(f"Error removing group {chat_id}: {e}")
            return False
    
    async def mark_group_inactive(self, chat_id):
        """Mark a group as inactive (bot can't send messages)"""
        try:
            await self.groups.update_one(
                {'chat_id': int(chat_id)},
                {'$set': {'is_active': False}}
            )
            logger.info(f"Group {chat_id} marked as inactive")
        except Exception as e:
            logger.error(f"Error marking group {chat_id} as inactive: {e}")
    
    async def get_all_groups(self):
        """Get all active groups"""
        try:
            groups = []
            async for group in self.groups.find({'is_active': True}):
                groups.append(group)
            return groups
        except Exception as e:
            logger.error(f"Error getting all groups: {e}")
            return []
    
    async def total_groups_count(self):
        """Get total groups count"""
        try:
            count = await self.groups.count_documents({})
            return count
        except Exception as e:
            logger.error(f"Error counting groups: {e}")
            return 0
    
    async def active_groups_count(self):
        """Get active groups count"""
        try:
            count = await self.groups.count_documents({'is_active': True})
            return count
        except Exception as e:
            logger.error(f"Error counting active groups: {e}")
            return 0


# Initialize database instance
db = Database(DATABASE_URI, DATABASE_NAME)
