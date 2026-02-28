import re
import logging
import asyncio
import hashlib
import json
from pyrogram import Client
from pyrogram.errors import FloodWait, MessageNotModified
from database.series_db import db
from info import UPDATE_CHANNEL

logger = logging.getLogger(__name__)


# ============================================================
# Helpers for episode formatting
# ============================================================

def _ep_num(name: str) -> int:
    """Extract episode number from name like 'Episode 5' or 'E05'."""
    m = re.search(r'\d+', name)
    return int(m.group()) if m else 0


def _format_ep_range(ep_nums: list) -> str:
    """
    Format sorted list of episode numbers into compact string.
    [1]     -> 'E01'
    [1,2,3] -> 'E01-E03'
    [1,3]   -> 'E01,E03'
    """
    nums = sorted(set(ep_nums))
    if not nums:
        return ''
    if len(nums) == 1:
        return f"E{nums[0]:02d}"
    if nums == list(range(nums[0], nums[-1] + 1)):
        return f"E{nums[0]:02d}-E{nums[-1]:02d}"
    return ','.join(f"E{n:02d}" for n in nums)


def _season_num(name: str) -> int:
    """Extract season number from 'Season 1' etc."""
    m = re.search(r'\d+', name)
    return int(m.group()) if m else 0


def _season_code(name: str) -> str:
    """'Season 1' -> 'S01'"""
    m = re.search(r'\d+', name)
    return f"S{int(m.group()):02d}" if m else name


# ============================================================
# Content snapshot (for duplicate-prevention)
# ============================================================

def _build_content_snapshot(series_data: dict) -> str:
    """
    Build a stable MD5 hash of the series' actual publishable content:
    batch qualities and episode files only.

    Poster URL, caption, and other non-content fields are excluded.
    If snapshot matches the stored one, we skip update message.
    """
    snapshot = {}

    languages = series_data.get('languages', {})
    for lang_id, lang_data in sorted(languages.items()):
        lang_snap = {}
        seasons = lang_data.get('seasons', {})
        for season_id, season_data in sorted(seasons.items()):
            season_snap = {}

            # Batch qualities
            qualities = season_data.get('qualities', {})
            published_batches = sorted([
                q.get('name', '')
                for q in qualities.values()
                if q.get('published', False) and q.get('batch_link')
            ])
            if published_batches:
                season_snap['batches'] = published_batches

            # Episodes
            episodes = season_data.get('episodes', {})
            ep_snap = {}
            for ep_id, ep_data in sorted(episodes.items()):
                ep_quals = sorted([
                    q.get('name', '')
                    for q in ep_data.get('qualities', {}).values()
                    if q.get('published', False) and q.get('file_link')
                ])
                if ep_quals:
                    ep_snap[ep_data.get('name', ep_id)] = ep_quals
            if ep_snap:
                season_snap['episodes'] = ep_snap

            if season_snap:
                lang_snap[season_data.get('name', season_id)] = season_snap

        if lang_snap:
            snapshot[lang_data.get('name', lang_id)] = lang_snap

    raw = json.dumps(snapshot, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


# ============================================================
# Message formatter
# ============================================================

async def format_series_update_message(series_data: dict) -> str:
    """
    Format the series update message including both batch seasons and episodes.

    Format per language section:
      Language : English
      S01 : 720p.H.265, 1080p.H.265          <- batch season
      S02E01 : 720p.H.265                     <- single episode
      S03E01-E05 : 720p.H.265, 1080p.H.265   <- episode range (same qualities)
    """
    title = series_data.get('title', 'Unknown Series')
    year = series_data.get('year', '')

    message = f"<code>{title}"
    if year:
        message += f" ({year})"
    message += "</code>\n\n"

    languages = series_data.get('languages', {})

    if not languages:
        return message + "<i>No content available yet.</i>"

    any_lang_shown = False

    for lang_id, lang_data in languages.items():
        lang_name = lang_data.get('name', 'Unknown')
        seasons = lang_data.get('seasons', {})

        season_lines = []

        # Sort seasons by number
        sorted_seasons = sorted(seasons.items(), key=lambda x: _season_num(x[1].get('name', '')))

        for season_id, season_data in sorted_seasons:
            season_name = season_data.get('name', '')
            s_code = _season_code(season_name)

            # --- Batch qualities ---
            qualities = season_data.get('qualities', {})
            published_batches = [
                q.get('name', '')
                for q in qualities.values()
                if q.get('published', False) and q.get('batch_link')
            ]
            if published_batches:
                qualities_str = ", ".join(published_batches)
                season_lines.append(f"{s_code} : {qualities_str}")

            # --- Episode qualities ---
            # Group episodes by their set of quality names so we can show ranges
            # e.g.  E01, E02, E03 all with "720p.H.265" -> S01E01-E03 : 720p.H.265
            episodes = season_data.get('episodes', {})
            qual_to_eps: dict = {}
            for ep_id, ep_data in episodes.items():
                ep_quals = tuple(sorted(
                    q.get('name', '')
                    for q in ep_data.get('qualities', {}).values()
                    if q.get('published', False) and q.get('file_link')
                ))
                if ep_quals:
                    ep_n = _ep_num(ep_data.get('name', ''))
                    qual_to_eps.setdefault(ep_quals, []).append(ep_n)

            # Sort groups by lowest episode number
            for ep_quals, ep_nums in sorted(qual_to_eps.items(), key=lambda x: min(x[1])):
                ep_str = _format_ep_range(ep_nums)
                qualities_str = ", ".join(ep_quals)
                season_lines.append(f"{s_code}{ep_str} : {qualities_str}")

        if season_lines:
            any_lang_shown = True
            message += f"<b>Language : {lang_name}</b>\n"
            message += "\n".join(season_lines)
            message += "\n\n"

    message = message.rstrip()

    if not any_lang_shown:
        message += "\n<i>No content available yet.</i>"

    return message


# ============================================================
# Send / update logic
# ============================================================

async def send_or_update_series_message(client: Client, series_id: str):
    """
    Send a new update message or edit the existing one.
    ONLY triggers when actual content (batches/episodes) has changed.
    Poster updates, caption updates, and no-change publishes are ignored.
    """
    if not UPDATE_CHANNEL:
        logger.warning("UPDATE_CHANNEL not configured")
        return False

    try:
        series = await db.get_series(series_id)
        if not series:
            logger.error(f"Series {series_id} not found")
            return False

        if not series.get('published', False):
            logger.info(f"Series {series_id} is not published, skipping update message")
            return True

        # Build content snapshot — skip if nothing changed
        new_snapshot = _build_content_snapshot(series)
        stored_snapshot = series.get('update_content_snapshot')

        if stored_snapshot and stored_snapshot == new_snapshot:
            logger.info(f"No content change for '{series.get('title')}', skipping update message")
            return True

        message_text = await format_series_update_message(series)
        update_msg_id = series.get('update_message_id')

        if update_msg_id:
            try:
                await client.edit_message_text(
                    chat_id=UPDATE_CHANNEL,
                    message_id=update_msg_id,
                    text=message_text
                )
                logger.info(f"Edited update message for '{series.get('title')}'")
                await db.set_update_content_snapshot(series_id, new_snapshot)
                return True
            except MessageNotModified:
                await db.set_update_content_snapshot(series_id, new_snapshot)
                return True
            except Exception as e:
                logger.error(f"Failed to edit message {update_msg_id}: {e}")
                update_msg_id = None

        if not update_msg_id:
            try:
                sent_message = await client.send_message(
                    chat_id=UPDATE_CHANNEL,
                    text=message_text
                )
                await db.set_update_message_id(series_id, sent_message.id)
                await db.set_update_content_snapshot(series_id, new_snapshot)
                logger.info(f"Sent new update message for '{series.get('title')}'")
                return True
            except FloodWait as e:
                logger.warning(f"FloodWait: Waiting {e.value} seconds")
                await asyncio.sleep(e.value)
                return await send_or_update_series_message(client, series_id)
            except Exception as e:
                logger.error(f"Failed to send update message: {e}")
                return False

    except Exception as e:
        logger.error(f"Error in send_or_update_series_message: {e}", exc_info=True)
        return False


async def delete_series_update_message(client: Client, series_id: str):
    """Delete the update message for a series from the update channel."""
    if not UPDATE_CHANNEL:
        logger.warning("UPDATE_CHANNEL not configured")
        return False

    try:
        series = await db.get_series(series_id)
        if not series:
            logger.error(f"Series {series_id} not found")
            return False

        update_msg_id = series.get('update_message_id')

        if update_msg_id:
            try:
                await client.delete_messages(
                    chat_id=UPDATE_CHANNEL,
                    message_ids=update_msg_id
                )
                logger.info(f"Deleted update message {update_msg_id} for {series.get('title')}")
                await db.set_update_message_id(series_id, None)
                return True
            except Exception as e:
                logger.error(f"Failed to delete message {update_msg_id}: {e}")
                return False
        else:
            logger.info(f"No update message to delete for series {series_id}")
            return True

    except Exception as e:
        logger.error(f"Error in delete_series_update_message: {e}", exc_info=True)
        return False
