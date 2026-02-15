import motor.motor_asyncio
from info import DATABASE_URI, DATABASE_NAME
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ChatDatabase:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.banned_users = self.db.banned_users
        self.chats = self.db.chats
    
    # =================== BAN/UNBAN USERS ===================
    
    async def ban_user(self, user_id):
        """Ban a user from using the bot"""
        try:
            await self.banned_users.update_one(
                {'user_id': int(user_id)},
                {
                    '$set': {
                        'user_id': int(user_id),
                        'banned_at': datetime.now()
                    }
                },
                upsert=True
            )
            logger.info(f"User {user_id} banned")
            return True
        except Exception as e:
            logger.error(f"Error banning user {user_id}: {e}")
            return False
    
    async def unban_user(self, user_id):
        """Unban a user"""
        try:
            result = await self.banned_users.delete_one({'user_id': int(user_id)})
            if result.deleted_count > 0:
                logger.info(f"User {user_id} unbanned")
                return True
            return False
        except Exception as e:
            logger.error(f"Error unbanning user {user_id}: {e}")
            return False
    
    async def is_user_banned(self, user_id):
        """Check if user is banned"""
        user = await self.banned_users.find_one({'user_id': int(user_id)})
        return bool(user)
    
    async def get_banned_users(self):
        """Get list of all banned users"""
        try:
            users = []
            async for user in self.banned_users.find({}):
                users.append(user)
            return users
        except Exception as e:
            logger.error(f"Error getting banned users: {e}")
            return []
    
    # =================== CHAT ENABLE/DISABLE ===================
    
    async def enable_chat(self, chat_id):
        """Enable bot in a chat"""
        try:
            await self.chats.update_one(
                {'chat_id': int(chat_id)},
                {
                    '$set': {
                        'chat_id': int(chat_id),
                        'is_disabled': False,
                        'updated_at': datetime.now()
                    }
                },
                upsert=True
            )
            logger.info(f"Chat {chat_id} enabled")
            return True
        except Exception as e:
            logger.error(f"Error enabling chat {chat_id}: {e}")
            return False
    
    async def disable_chat(self, chat_id):
        """Disable bot in a chat"""
        try:
            await self.chats.update_one(
                {'chat_id': int(chat_id)},
                {
                    '$set': {
                        'chat_id': int(chat_id),
                        'is_disabled': True,
                        'updated_at': datetime.now()
                    }
                },
                upsert=True
            )
            logger.info(f"Chat {chat_id} disabled")
            return True
        except Exception as e:
            logger.error(f"Error disabling chat {chat_id}: {e}")
            return False
    
    async def is_chat_disabled(self, chat_id):
        """Check if chat is disabled"""
        chat = await self.chats.find_one({'chat_id': int(chat_id)})
        if chat:
            return chat.get('is_disabled', False)
        return False
    
    async def get_enabled_chats(self):
        """Get list of all enabled chats"""
        try:
            chats = []
            async for chat in self.chats.find({'is_disabled': False}):
                chats.append(chat)
            return chats
        except Exception as e:
            logger.error(f"Error getting enabled chats: {e}")
            return []
    
    async def get_disabled_chats(self):
        """Get list of all disabled chats"""
        try:
            chats = []
            async for chat in self.chats.find({'is_disabled': True}):
                chats.append(chat)
            return chats
        except Exception as e:
            logger.error(f"Error getting disabled chats: {e}")
            return []
    
    async def get_all_chats(self):
        """Get all chats"""
        try:
            chats = []
            async for chat in self.chats.find({}):
                chats.append(chat)
            return chats
        except Exception as e:
            logger.error(f"Error getting all chats: {e}")
            return []


# Initialize database instance
chat_db = ChatDatabase(DATABASE_URI, DATABASE_NAME)
