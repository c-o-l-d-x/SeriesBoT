"""
Recent List Manager
Handles building, sending, and editing the recently-added series list in a channel.

Format (image 2 style):
  1. Shoresy S01E01,E02
  2. Locke & Key S02E02
  3. How I Met Your Father S01
  4. Alice in Borderland S01E01-E05
  5. Animal Control S01,S02E01
"""

import logging
from pyrogram import Client
from pyrogram.errors import MessageIdInvalid, MessageNotModified, ChatAdminRequired
from database.series_db import db
from database.recent_list_db import recent_list_db

logger = logging.getLogger(__name__)


# ============================================================
# Build info_str for one series at publish time
# ============================================================

def _build_info_str(series_data: dict) -> str:
    """
    Build the season/episode info string for one series.
    Only shows the NEWLY published content (what is currently in the DB).

    Rules:
    - Season batch only  → S01
    - 1 episode          → S01E01
    - 2 non-consecutive  → S01E01,E02
    - consecutive range  → S01E01-E05
    - Mixed season+ep    → S01,S02E01
    """
    parts = []

    languages = series_data.get('languages', {})
    for lang_id, lang_data in languages.items():
        seasons = lang_data.get('seasons', {})
        for season_id, season_data in seasons.items():
            season_name = season_data.get('name', '')
            # Extract season number (e.g. "Season 1" → "S01")
            s_code = _season_code(season_name)

            qualities = season_data.get('qualities', {})
            has_batch = any(
                q.get('published', False) and q.get('batch_link')
                for q in qualities.values()
            )

            episodes = season_data.get('episodes', {})
            published_eps = []
            for ep_id, ep_data in episodes.items():
                if any(
                    q.get('published', False) and q.get('file_link')
                    for q in ep_data.get('qualities', {}).values()
                ):
                    published_eps.append(ep_data.get('name', ''))

            if has_batch and not published_eps:
                # Whole season batch
                parts.append(s_code)
            elif published_eps:
                ep_str = _format_episodes(published_eps)
                parts.append(f"{s_code}{ep_str}")
            elif has_batch:
                parts.append(s_code)

    if not parts:
        return ''

    return _compact_parts(parts)


def _season_code(season_name: str) -> str:
    """Convert 'Season 1' → 'S01', 'Season 12' → 'S12', fallback → raw."""
    import re
    m = re.search(r'\d+', season_name)
    if m:
        return f"S{int(m.group()):02d}"
    return season_name


def _format_episodes(ep_names: list) -> str:
    """
    Given list like ['E01','E02','E03'] → 'E01-E03'
    ['E01','E03'] → 'E01,E03'
    ['E01'] → 'E01'
    """
    import re

    def ep_num(name):
        m = re.search(r'\d+', name)
        return int(m.group()) if m else None

    nums = []
    for n in ep_names:
        num = ep_num(n)
        if num is not None:
            nums.append(num)

    if not nums:
        return ','.join(ep_names)

    nums = sorted(set(nums))

    if len(nums) == 1:
        return f"E{nums[0]:02d}"

    # Check if consecutive
    if nums == list(range(nums[0], nums[-1] + 1)):
        return f"E{nums[0]:02d}-E{nums[-1]:02d}"
    else:
        return ','.join(f"E{n:02d}" for n in nums)


def _compact_parts(parts: list) -> str:
    """
    Compact multiple parts:
    ['S01', 'S02E01'] → 'S01,S02E01'
    ['S01E01-E05'] → 'S01E01-E05'
    """
    return ','.join(parts)


# ============================================================
# Format the full channel message from entries list
# ============================================================

def _format_channel_message(entries: list) -> str:
    """Build the full text for the channel message (image 2 style)."""
    lines = ["⚡ <b>Recently Added Series</b> ⚡\n"]
    for idx, entry in enumerate(entries, 1):
        title = entry.get('title', 'Unknown')
        info_str = entry.get('info_str', '')
        if info_str:
            lines.append(f"{idx}. <b>{title}</b> {info_str}")
        else:
            lines.append(f"{idx}. <b>{title}</b>")
    return '\n'.join(lines)


# ============================================================
# Public API
# ============================================================

async def handle_recent_command(client: Client, channel_id: int):
    """
    Called when admin runs /recent {channel_id}.
    Sends or re-sends the recent list to that channel.
    """
    # Save channel_id
    await recent_list_db.set_config(channel_id)

    entries = await recent_list_db.get_entries()
    if not entries:
        # Send placeholder
        text = "⚡ <b>Recently Added Series</b> ⚡\n\n<i>No series added yet.</i>"
    else:
        text = _format_channel_message(entries)

    try:
        sent = await client.send_message(chat_id=channel_id, text=text)
        await recent_list_db.set_message_id(sent.id)
        logger.info(f"Sent recent list to channel {channel_id}, msg_id={sent.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send recent list to channel {channel_id}: {e}")
        return False


async def update_recent_list(client: Client, series_id: str):
    """
    Called after a series is published/updated.
    Adds/updates the entry in recent list and edits the channel message.
    """
    series = await db.get_series(series_id)
    if not series:
        return

    if not series.get('published', False):
        return

    title = series.get('title', 'Unknown')
    info_str = _build_info_str(series)

    if not info_str:
        # Nothing meaningful to show
        return

    # Upsert entry (moves to top, removes oldest if >10)
    await recent_list_db.upsert_entry(series_id, title, info_str)

    # Get updated entries and channel config
    entries = await recent_list_db.get_entries()
    config = await recent_list_db.get_config()

    if not config or not config.get('channel_id'):
        logger.info("Recent list: no channel configured yet, skipping message update.")
        return

    channel_id = config['channel_id']
    message_id = config.get('message_id')
    text = _format_channel_message(entries)

    if message_id:
        # Try to edit existing message
        try:
            await client.edit_message_text(
                chat_id=channel_id,
                message_id=message_id,
                text=text
            )
            logger.info(f"Edited recent list message {message_id} in channel {channel_id}")
            return
        except MessageNotModified:
            return
        except (MessageIdInvalid, Exception) as e:
            # Message was deleted or any other error → clear stored id, send new
            logger.warning(f"Could not edit recent list message ({e}), will send new one.")
            await recent_list_db.clear_message_id()
            message_id = None

    # Send new message
    if not message_id:
        try:
            sent = await client.send_message(chat_id=channel_id, text=text)
            await recent_list_db.set_message_id(sent.id)
            logger.info(f"Sent new recent list message to channel {channel_id}")
        except Exception as e:
            logger.error(f"Failed to send recent list to channel {channel_id}: {e}")
