from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.series = self.db['series']
        self.caption_templates = self.db['caption_templates']  # NEW: For dynamic caption templates
    
    async def add_series(self, series_id, title, year='', genre='', rating='', imdb_id='', poster_url=''):
        """Add a new series"""
        from datetime import datetime
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {
                'title': title,
                'year': year,
                'genre': genre,
                'rating': rating,
                'imdb_id': imdb_id,
                'poster_id': None,
                'poster_url': poster_url,
                'languages': {},
                'published': False,  # New field for publish status
                'update_message_id': None,  # ID of update message in UPDATE_CHANNEL
                'created_at': datetime.utcnow()
            }},
            upsert=True
        )
    
    async def get_series(self, series_id):
        """Get series by ID"""
        return await self.series.find_one({'_id': series_id})
    
    async def get_all_series(self):
        """Get all series"""
        cursor = self.series.find({})
        return await cursor.to_list(length=None)
    
    async def get_published_series(self):
        """Get only published series"""
        cursor = self.series.find({'published': True})
        return await cursor.to_list(length=None)
    
    async def series_exists(self, imdb_id=None, title=None):
        """
        Check if a series already exists by IMDB ID or title
        
        Args:
            imdb_id: The IMDB ID to check
            title: The series title to check (case-insensitive)
        
        Returns:
            dict: The existing series if found, None otherwise
        """
        try:
            query = {}
            
            if imdb_id:
                # First try to find by IMDB ID (most reliable)
                query['imdb_id'] = imdb_id
                existing = await self.series.find_one(query)
                if existing:
                    return existing
            
            if title:
                # If not found by IMDB ID, try by title (case-insensitive)
                query = {'title': {'$regex': f'^{title}$', '$options': 'i'}}
                existing = await self.series.find_one(query)
                if existing:
                    return existing
            
            return None
        
        except Exception as e:
            logger.error(f"Error checking series existence: {e}", exc_info=True)
            return None
    
    async def publish_series(self, series_id, published=True):
        """Publish or unpublish a series"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {'published': published}}
        )
    
    async def add_language(self, series_id, lang_id, lang_name):
        """Add language to series"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {f'languages.{lang_id}': {
                'name': lang_name,
                'poster_id': None,
                'seasons': {}
            }}}
        )
    
    async def add_season(self, series_id, lang_id, season_id, season_name):
        """Add season to language"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {f'languages.{lang_id}.seasons.{season_id}': {
                'name': season_name,
                'poster_id': None,
                'qualities': {}
            }}}
        )
    
    async def add_quality(self, series_id, lang_id, season_id, quality_id, quality_name):
        """Add quality to season"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {f'languages.{lang_id}.seasons.{season_id}.qualities.{quality_id}': {
                'name': quality_name,
                'first_msg_id': None,
                'last_msg_id': None,
                'db_channel_id': None,
                'batch_link': None,
                'published': False
            }}}
        )
    
    async def set_batch_range(self, series_id, lang_id, season_id, quality_id, first_msg_id, last_msg_id, db_channel_id):
        """Set batch message range - ONLY stores message IDs, not files"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {
                f'languages.{lang_id}.seasons.{season_id}.qualities.{quality_id}.first_msg_id': first_msg_id,
                f'languages.{lang_id}.seasons.{season_id}.qualities.{quality_id}.last_msg_id': last_msg_id,
                f'languages.{lang_id}.seasons.{season_id}.qualities.{quality_id}.db_channel_id': db_channel_id
            }}
        )
    
    async def update_quality_batch(self, series_id, lang_id, season_id, quality_id, batch_link):
        """Update quality with batch link"""
        await self.series.update_one(
            {'_id': series_id},
            {
                '$set': {
                    f'languages.{lang_id}.seasons.{season_id}.qualities.{quality_id}.batch_link': batch_link,
                    f'languages.{lang_id}.seasons.{season_id}.qualities.{quality_id}.published': True
                }
            }
        )
    
    async def publish_quality(self, series_id, lang_id, season_id, quality_id, published=True):
        """Publish or unpublish quality"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {f'languages.{lang_id}.seasons.{season_id}.qualities.{quality_id}.published': published}}
        )
    
    async def update_poster(self, series_id, poster_id, lang_id=None, season_id=None):
        """Update poster file ID"""
        if lang_id and season_id:
            field = f'languages.{lang_id}.seasons.{season_id}.poster_id'
        elif lang_id:
            field = f'languages.{lang_id}.poster_id'
        else:
            field = 'poster_id'
        
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {field: poster_id}}
        )
    
    async def update_series_poster(self, series_id, poster_url):
        """Update series poster URL"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {'poster_url': poster_url}}
        )
    
    async def update_series_details(self, series_id, details):
        """Update series details (title, year, genre, rating)"""
        update_fields = {}
        
        if 'title' in details:
            update_fields['title'] = details['title']
        if 'year' in details:
            update_fields['year'] = details['year']
        if 'genre' in details:
            update_fields['genre'] = details['genre']
        if 'rating' in details:
            update_fields['rating'] = details['rating']
        
        if update_fields:
            await self.series.update_one(
                {'_id': series_id},
                {'$set': update_fields}
            )
    
    async def delete_language(self, series_id, lang_id):
        """Delete language"""
        await self.series.update_one(
            {'_id': series_id},
            {'$unset': {f'languages.{lang_id}': ''}}
        )
    
    async def delete_season(self, series_id, lang_id, season_id):
        """Delete season"""
        await self.series.update_one(
            {'_id': series_id},
            {'$unset': {f'languages.{lang_id}.seasons.{season_id}': ''}}
        )
    
    async def delete_quality(self, series_id, lang_id, season_id, quality_id):
        """Delete quality"""
        await self.series.update_one(
            {'_id': series_id},
            {'$unset': {f'languages.{lang_id}.seasons.{season_id}.qualities.{quality_id}': ''}}
        )

    # ============================================================
    # EPISODE METHODS (Single episode file support)
    # ============================================================

    async def add_episode(self, series_id, lang_id, season_id, episode_id, episode_name):
        """Add episode to season"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {f'languages.{lang_id}.seasons.{season_id}.episodes.{episode_id}': {
                'name': episode_name,
                'qualities': {}
            }}}
        )

    async def add_episode_quality(self, series_id, lang_id, season_id, episode_id, quality_id, quality_name):
        """Add quality to episode"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {f'languages.{lang_id}.seasons.{season_id}.episodes.{episode_id}.qualities.{quality_id}': {
                'name': quality_name,
                'file_link': None,
                'msg_id': None,
                'published': False
            }}}
        )

    async def set_episode_quality_file(self, series_id, lang_id, season_id, episode_id, quality_id, msg_id, file_link):
        """Set file message id and link for episode quality"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {
                f'languages.{lang_id}.seasons.{season_id}.episodes.{episode_id}.qualities.{quality_id}.msg_id': msg_id,
                f'languages.{lang_id}.seasons.{season_id}.episodes.{episode_id}.qualities.{quality_id}.file_link': file_link,
                f'languages.{lang_id}.seasons.{season_id}.episodes.{episode_id}.qualities.{quality_id}.published': True
            }}
        )

    async def delete_episode(self, series_id, lang_id, season_id, episode_id):
        """Delete episode"""
        await self.series.update_one(
            {'_id': series_id},
            {'$unset': {f'languages.{lang_id}.seasons.{season_id}.episodes.{episode_id}': ''}}
        )

    async def delete_episode_quality(self, series_id, lang_id, season_id, episode_id, quality_id):
        """Delete episode quality"""
        await self.series.update_one(
            {'_id': series_id},
            {'$unset': {f'languages.{lang_id}.seasons.{season_id}.episodes.{episode_id}.qualities.{quality_id}': ''}}
        )

    async def clear_episodes(self, series_id, lang_id, season_id):
        """Clear all episodes from a season"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {f'languages.{lang_id}.seasons.{season_id}.episodes': {}}}
        )

    async def delete_series(self, series_id):
        """Delete entire series"""
        result = await self.series.delete_one({'_id': series_id})
        return result.deleted_count > 0
    
    async def delete_all_series(self):
        """Delete all series"""
        result = await self.series.delete_many({})
        return result.deleted_count
    
    async def get_series_count(self):
        """Get total series count"""
        return await self.series.count_documents({})
    
    async def get_recent_series(self, limit=10):
        """Get recent series ordered by creation date"""
        cursor = self.series.find({}).sort('created_at', -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def set_update_message_id(self, series_id, message_id):
        """Set the update message ID for a series"""
        await self.series.update_one(
            {'_id': series_id},
            {'$set': {'update_message_id': message_id}}
        )
    
    async def get_update_message_id(self, series_id):
        """Get the update message ID for a series"""
        series = await self.series.find_one({'_id': series_id})
        return series.get('update_message_id') if series else None
    
    # ============================================================================
    # CAPTION TEMPLATE METHODS
    # ============================================================================
    
    async def save_caption_template(self, user_id: int, template: str):
        """Save caption template for user"""
        try:
            await self.caption_templates.update_one(
                {'user_id': user_id},
                {'$set': {'template': template}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error saving caption template: {e}", exc_info=True)
            return False
    
    async def get_caption_template(self, user_id: int):
        """Get caption template for user"""
        try:
            result = await self.caption_templates.find_one({'user_id': user_id})
            return result.get('template') if result else None
        except Exception as e:
            logger.error(f"Error getting caption template: {e}", exc_info=True)
            return None
    
    async def delete_caption_template(self, user_id: int):
        """Delete caption template for user"""
        try:
            await self.caption_templates.delete_one({'user_id': user_id})
            return True
        except Exception as e:
            logger.error(f"Error deleting caption template: {e}", exc_info=True)
            return False

# Initialize database
db = Database(DATABASE_URI, DATABASE_NAME)
