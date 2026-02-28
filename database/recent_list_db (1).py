"""
Recent List Database Module
Manages the persistent recent series list (entries + channel message ID).
"""

from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RecentListDB:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db['recent_list']

    # ------------------------------------------------------------------ #
    # CONFIG DOC  (_id = "config")
    # Stores: channel_id, message_id
    # ------------------------------------------------------------------ #

    async def get_config(self):
        """Get the config doc (channel_id + message_id)."""
        return await self.col.find_one({'_id': 'config'})

    async def set_config(self, channel_id: int, message_id=None):
        """Save / update channel_id and optionally message_id."""
        update = {'channel_id': channel_id}
        if message_id is not None:
            update['message_id'] = message_id
        await self.col.update_one(
            {'_id': 'config'},
            {'$set': update},
            upsert=True
        )

    async def set_message_id(self, message_id):
        """Update only the stored message_id."""
        await self.col.update_one(
            {'_id': 'config'},
            {'$set': {'message_id': message_id}},
            upsert=True
        )

    async def clear_message_id(self):
        """Clear the stored message_id (e.g. when the message was deleted)."""
        await self.col.update_one(
            {'_id': 'config'},
            {'$unset': {'message_id': ''}},
            upsert=False
        )

    # ------------------------------------------------------------------ #
    # ENTRIES DOC  (_id = "entries")
    # Stores: list of entry dicts, max 10
    # Each entry: {series_id, title, info_str, added_at}
    # ------------------------------------------------------------------ #

    async def get_entries(self):
        """Return the entries list (up to 10)."""
        doc = await self.col.find_one({'_id': 'entries'})
        return doc.get('items', []) if doc else []

    async def upsert_entry(self, series_id: str, title: str, info_str: str):
        """
        Add or update an entry for series_id.
        - If already present → update info_str and move to top (most recent).
        - If new → prepend; if list exceeds 10 → remove the last (oldest).
        """
        entries = await self.get_entries()

        # Remove existing entry for this series (if any)
        entries = [e for e in entries if e.get('series_id') != series_id]

        # Prepend new entry
        new_entry = {
            'series_id': series_id,
            'title': title,
            'info_str': info_str,
            'added_at': datetime.utcnow().isoformat()
        }
        entries.insert(0, new_entry)

        # Keep max 10
        entries = entries[:10]

        await self.col.update_one(
            {'_id': 'entries'},
            {'$set': {'items': entries}},
            upsert=True
        )

    async def get_entry(self, series_id: str):
        """Get the entry for a specific series_id, or None."""
        entries = await self.get_entries()
        for e in entries:
            if e.get('series_id') == series_id:
                return e
        return None

    async def set_entries(self, entries: list):
        """Overwrite the entire entries list (used when removing an entry)."""
        await self.col.update_one(
            {'_id': 'entries'},
            {'$set': {'items': entries}},
            upsert=True
        )


recent_list_db = RecentListDB(DATABASE_URI, DATABASE_NAME)
