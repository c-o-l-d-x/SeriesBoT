"""
Database module for batch message management
Handles storing message mappings from source channel to Main DB
"""

from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME
import logging

logger = logging.getLogger(__name__)

class BatchDatabase:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.batch_messages = self.db['batch_messages']
    
    async def store_batch_mapping(self, quality_key, source_first_id, source_last_id, 
                                   main_db_first_id, main_db_last_id, source_channel_id):
        """
        Store mapping between source channel messages and Main DB messages
        
        Args:
            quality_key: Unique key for the quality (series_id:lang_id:season_id:quality_id)
            source_first_id: First message ID from source channel
            source_last_id: Last message ID from source channel
            main_db_first_id: First message ID in Main DB
            main_db_last_id: Last message ID in Main DB
            source_channel_id: ID of the source channel
        """
        await self.batch_messages.update_one(
            {'_id': quality_key},
            {'$set': {
                'source_channel_id': source_channel_id,
                'source_first_id': source_first_id,
                'source_last_id': source_last_id,
                'main_db_first_id': main_db_first_id,
                'main_db_last_id': main_db_last_id
            }},
            upsert=True
        )
    
    async def get_batch_mapping(self, quality_key):
        """Get batch mapping by quality key"""
        return await self.batch_messages.find_one({'_id': quality_key})
    
    async def delete_batch_mapping(self, quality_key):
        """Delete batch mapping"""
        result = await self.batch_messages.delete_one({'_id': quality_key})
        return result.deleted_count > 0

# Initialize database
batch_db = BatchDatabase(DATABASE_URI, DATABASE_NAME)
