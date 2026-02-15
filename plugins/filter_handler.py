from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.filters_mdb import find_filter, find_gfilter
from utils import parse_buttons
import re


async def send_filter_reply(client, message, reply_text, btn, fileid, alert):
    """Send filter reply with proper formatting"""
    try:
        # Parse buttons if available
        keyboard = None
        if btn and btn != "[]" and btn != "None":
            keyboard = parse_buttons(btn)
        
        # Send reply based on file type
        if fileid and fileid != "None":
            # Has media
            if reply_text and reply_text != "None":
                caption = reply_text
            else:
                caption = ""
            
            try:
                await message.reply_cached_media(
                    file_id=fileid,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode=enums.ParseMode.HTML
                )
            except:
                # If cached media fails, try as document
                await message.reply_document(
                    document=fileid,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode=enums.ParseMode.HTML
                )
        else:
            # Text only
            if reply_text and reply_text != "None":
                await message.reply_text(
                    text=reply_text,
                    reply_markup=keyboard,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                )
    except Exception as e:
        print(f"Error sending filter reply: {e}")


@Client.on_message(
    filters.text & 
    filters.group & 
    filters.incoming & 
    ~filters.command(['start', 'help', 'about', 'filter', 'add', 'del', 'delall', 'viewfilters', 'filters']),
    group=1  # Use group 1 to ensure series search (group 0) runs first
)
async def filter_reply(client, message):
    """Respond to messages that match filters"""
    if not message.text:
        return
    
    group_id = message.chat.id
    query_text = message.text.lower()
    
    # Try to find exact match first in group filters
    reply_text, btn, alert, fileid = await find_filter(group_id, query_text)
    
    # If no group filter found, try global filters
    if not reply_text or reply_text == "None":
        reply_text, btn, alert, fileid = await find_gfilter('gfilters', query_text)
    
    # If filter found, send reply
    if reply_text and reply_text != "None":
        await send_filter_reply(client, message, reply_text, btn, fileid, alert)


@Client.on_message(
    filters.text & 
    filters.private & 
    filters.incoming &
    ~filters.command([
        'start', 'help', 'about', 
        'connect', 'disconnect', 'connections',
        'gfilter', 'addg', 'delg', 'delallg', 'viewgfilters', 'gfilters',
        'newseries', 'allseries', 'deleteseries', 'deleteall', 'editseries', 'recent',
        'broadcast', 'broadcasttext', 'groupbroadcast',
        'users', 'ban', 'unban', 'banned',
        'ping', 'fsub', 'fsub_channel', 'fsub_message', 'fsub_enable', 'fsub_disable', 'fsub_clear', 'fsub_stats'
    ]) &
    ~filters.forwarded &
    ~filters.regex(r't\.me/'),
    group=1  # Use group 1 to ensure series search (group 0) runs first
)
async def gfilter_pm_reply(client, message):
    """Respond to PM messages that match global filters"""
    if not message.text:
        return
    
    query_text = message.text.lower()
    
    # Try to find in global filters
    reply_text, btn, alert, fileid = await find_gfilter('gfilters', query_text)
    
    # Only send reply if filter found
    if reply_text and reply_text != "None":
        await send_filter_reply(client, message, reply_text, btn, fileid, alert)
