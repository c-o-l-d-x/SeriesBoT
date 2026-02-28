import logging
from pyrogram import Client
from pyrogram.errors import MessageIdInvalid, MessageNotModified
from database.series_db import db
from database.recent_list_db import recent_list_db

logger = logging.getLogger(__name__)


# ============================================================
# Build info_str for one series at publish time
# ============================================================

def _build_info_str(series_data: dict) -> str:
    """
    Build the info string showing ONLY the latest season/episode added.

    Logic:
    - Find the highest season number across all languages.
    - Within that season, if individual episodes are published,
      show only the latest (highest) episode: e.g. S03E05
    - If only a batch exists for that season, show just the season: e.g. S03

    Examples:
      Added S01, S02, S03 batches      -> S03
      Added S03E05 episode             -> S03E05
      Added S01 batch + S02E01 ep      -> S02E01  (S02 is higher)
    """
    import re

    def season_num(name: str):
        m = re.search(r'\d+', name)
        return int(m.group()) if m else 0

    def ep_num(name: str):
        m = re.search(r'\d+', name)
        return int(m.group()) if m else 0

    # Collect all seasons across all languages
    # season_map: {season_number: {'s_code': 'S03', 'has_batch': bool, 'ep_nums': [...]}}
    season_map = {}

    languages = series_data.get('languages', {})
    for lang_id, lang_data in languages.items():
        seasons = lang_data.get('seasons', {})
        for season_id, season_data in seasons.items():
            season_name = season_data.get('name', '')
            s_num = season_num(season_name)
            s_code = _season_code(season_name)

            # Check for published batch
            qualities = season_data.get('qualities', {})
            has_batch = any(
                q.get('published', False) and q.get('batch_link')
                for q in qualities.values()
            )

            # Collect published episode numbers
            episodes = season_data.get('episodes', {})
            ep_nums = []
            for ep_id, ep_data in episodes.items():
                if any(
                    q.get('published', False) and q.get('file_link')
                    for q in ep_data.get('qualities', {}).values()
                ):
                    ep_nums.append(ep_num(ep_data.get('name', '')))

            # Skip seasons with no published content
            if not has_batch and not ep_nums:
                continue

            # Merge into season_map (same season number may exist across languages)
            if s_num not in season_map:
                season_map[s_num] = {'s_code': s_code, 'has_batch': has_batch, 'ep_nums': ep_nums}
            else:
                season_map[s_num]['has_batch'] = season_map[s_num]['has_batch'] or has_batch
                season_map[s_num]['ep_nums'] = list(set(season_map[s_num]['ep_nums'] + ep_nums))

    if not season_map:
        return ''

    # Find the highest season number - that is the "latest"
    latest_s_num = max(season_map.keys())
    latest = season_map[latest_s_num]
    s_code = latest['s_code']
    ep_nums = sorted(set(latest['ep_nums']))

    if ep_nums:
        # Show only the latest (highest numbered) episode in that season
        latest_ep = ep_nums[-1]
        return f"{s_code}E{latest_ep:02d}"
    else:
        # Batch only - just show the season code
        return s_code


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
    lines = ["<pre><b>⚡ Recently Added ⚡</b></pre>\n"]
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


async def remove_from_recent_list(client: Client, series_id: str):
    """
    Called when a series is deleted.
    Removes the entry from the recent list and updates the channel message.
    """
    entries = await recent_list_db.get_entries()
    # Check if this series is even in the list
    if not any(e.get('series_id') == series_id for e in entries):
        return

    # Remove the entry
    new_entries = [e for e in entries if e.get('series_id') != series_id]
    await recent_list_db.set_entries(new_entries)

    # Get channel config
    config = await recent_list_db.get_config()
    if not config or not config.get('channel_id'):
        return

    channel_id = config['channel_id']
    message_id = config.get('message_id')

    if new_entries:
        text = _format_channel_message(new_entries)
    else:
        text = "⚡ <b>Recently Added Series</b> ⚡\n\n<i>No series added yet.</i>"

    if message_id:
        try:
            await client.edit_message_text(
                chat_id=channel_id,
                message_id=message_id,
                text=text
            )
            logger.info(f"Removed series {series_id} from recent list message")
            return
        except MessageNotModified:
            return
        except (MessageIdInvalid, Exception) as e:
            logger.warning(f"Could not edit recent list after removal ({e}), sending new.")
            await recent_list_db.clear_message_id()
            message_id = None

    if not message_id:
        try:
            sent = await client.send_message(chat_id=channel_id, text=text)
            await recent_list_db.set_message_id(sent.id)
            logger.info(f"Sent new recent list after removing series {series_id}")
        except Exception as e:
            logger.error(f"Failed to send recent list after removal: {e}")
