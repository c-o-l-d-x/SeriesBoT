from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from pyrogram.errors import FloodWait
from database.series_db import db
from database.batch_db import batch_db  # NEW: For batch message mapping
from info import ADMINS, IMGBB_API_KEY, CUSTOM_FILE_CAPTION, MAIN_DB_CHANNEL
from .caption_handler import format_caption, get_caption_template
from state_manager import state_manager
from helpers.metadata_fetcher import metadata_fetcher
from helpers.spell_checker import spell_checker, check_series_spelling
from plugins.force_sub_handler import check_force_sub, send_force_sub_message
from auth_manager import auth_manager  # For auth user support
from .update_channel import send_or_update_series_message, delete_series_update_message  # For update channel
from .recent_list import update_recent_list  # For recent list channel
import logging
import uuid
import io
import asyncio
import requests
import base64
import random  # For random start messages

# Try different import paths for helper_func
try:
    from helper_func import get_message_id
except ImportError:
    try:
        from helpers.helper_func import get_message_id
    except ImportError:
        from ..helper_func import get_message_id

# Import broadcast database for user tracking
try:
    from database.database import db as broadcast_db
except ImportError:
    broadcast_db = None
    logging.warning("Broadcast database not found - user tracking disabled")

logger = logging.getLogger(__name__)


async def publish_update(client: Client, series_id: str):
    """Calls both update_channel and recent_list updates together."""
    await send_or_update_series_message(client, series_id)
    try:
        await update_recent_list(client, series_id)
    except Exception as e:
        logger.warning(f"recent_list update failed: {e}")

# ============================================================================
# RANDOM START MESSAGES
# ============================================================================

START_MESSAGES = [
    "<b>🎬 Every story begins with a title…</b>\n<i>Welcome to Series Bot.</i>\nSend the name of a series and step into the world.",
    
    "<b>Lights on. Episodes loaded.</b>\n<i>This is Series Bot.</i>\nType a series name and let the show begin.",
    
    "<b>A universe of stories awaits.</b>\n<i>Your journey starts here.</i>\nSend the series name.",
    
    "<b>From the first episode to the final scene…</b>\n<i>Series Bot is ready.</i>\nSearch any series to begin.",
    
    "<b>🎥 The screen fades in.</b>\n<i>The story starts now.</i>\nType a series name.",
    
    "<b>Every legend has seasons.</b>\n<i>Discover them with Series Bot.</i>\nSend the series title.",
    
    "<b>🎬 This is where binge nights are born.</b>\n<i>Welcome to Series Bot.</i>\nName the series you seek.",
    
    "<b>Your next chapter begins here.</b>\n<i>Series Bot awaits.</i>\nSend the series name.",
    
    "<b>Stories don't end.</b>\n<i>They continue in episodes.</i>\nSearch your series now.",
    
    "<b>🎞️ Press play on a new world.</b>\n<i>Series Bot is live.</i>\nType the series name.",
    
    "<b>🍿 Warning: Extreme binge-watching ahead!</b>\n<i>Side effects include no sleep.</i>\nSend a series name.",
    
    "<b>Can't find what to watch?</b>\n<i>Neither can humanity.</i>\nSend the series name 😌",
    
    "<b>I find series.</b>\n<i>You lose sleep.</i>\nFair trade? 😎",
    
    "<b>Your couch misses you.</b>\n<i>Let's fix that.</i>\nType the series name 🍿",
    
    "<b>Netflix is judging you.</b>\n<i>I am not.</i>\nSend the series name 😏",
    
    "<b>Procrastination detected.</b>\n<i>Engaging Series Bot.</i>\nSend a series name 🚀",
    
    "<b>Homework can wait.</b>\n<i>This episode can't.</i>\nType the series name 😄",
    
    "<b>One episode only.</b>\n<i>That's a lie.</i>\nSend the series name 😜",
    
    "<b>Sleep is optional.</b>\n<i>Good series are not.</i>\nSend the title 😴",
    
    "<b>Series Bot online.</b>\n<i>Productivity offline.</i>\nType the series name 😂"
]

# ============================================================================
# PERMISSION FILTER
# ============================================================================

async def auth_filter_func(_, __, message):
    """Custom filter function that dynamically checks if user is admin or auth user"""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return False
    # Check if user is admin or auth user (dynamically checked each time)
    return user_id in ADMINS or auth_manager.is_auth_user(user_id)

# Create the custom filter
auth_filter = filters.create(auth_filter_func)

# ============================================================================
# HELPER FUNCTIONS FOR BATCH
# ============================================================================

async def get_messages(client, message_ids):
    """Get messages from DB channel in batches of 200 - supports all message types"""
    messages = []
    total_messages = 0
    while total_messages != len(message_ids):
        temp_ids = message_ids[total_messages:total_messages+200]
        try:
            msgs = await client.get_messages(
                chat_id=client.main_db_channel.id,
                message_ids=temp_ids
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            msgs = await client.get_messages(
                chat_id=client.main_db_channel.id,
                message_ids=temp_ids
            )
        except:
            pass
        total_messages += len(temp_ids)
        messages.extend(msgs)
    return messages

# ============================================================================
# IMGBB UPLOAD HELPER
# ============================================================================

async def upload_to_imgbb(photo_path: str) -> str:
    """
    Upload photo to ImgBB and return the URL
    
    Args:
        photo_path: Local path to the photo file
        
    Returns:
        URL of uploaded image or empty string on failure
    """
    try:
        with open(photo_path, 'rb') as file:
            # Convert to base64
            image_data = base64.b64encode(file.read()).decode('utf-8')
        
        # Upload to ImgBB
        url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": IMGBB_API_KEY,
            "image": image_data
        }
        
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                # Use display_url (direct image link), fallback to image.url, then url
                data = result['data']
                return (
                    data.get('display_url') or
                    data.get('image', {}).get('url') or
                    data.get('url', '')
                )
        
        logger.error(f"ImgBB upload failed: {response.text}")
        return ""
    
    except Exception as e:
        logger.error(f"Error uploading to ImgBB: {e}", exc_info=True)
        return ""

# ============================================================================
# COMMAND HANDLERS
# ============================================================================

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Handle /start command and deep links - WITH USER TRACKING FOR BROADCAST"""
    
    # ============= USER TRACKING FOR BROADCAST SYSTEM =============
    # Track user for broadcast functionality
    if broadcast_db:
        user_id = message.from_user.id
        try:
            # Check if user exists in broadcast database
            if not await broadcast_db.is_user_exist(user_id):
                # Add new user to broadcast database
                await broadcast_db.add_user(user_id)
                logger.info(f"New user added to broadcast database: {user_id}")
            else:
                # Update last active time for existing user
                await broadcast_db.update_last_active(user_id)
                logger.info(f"User activity updated in broadcast database: {user_id}")
        except Exception as e:
            logger.error(f"Error tracking user in broadcast database: {e}")
    # ==============================================================
    
    # Check if there's a deep link parameter
    if len(message.command) > 1:
        deep_link = message.command[1]
        
        try:
            # Check if it's a series access link (format: series_<series_id>)
            if deep_link.startswith("series_"):
                series_id = deep_link.replace("series_", "")
                await show_user_series_view(message, series_id, client=client)
                return
            
            # ========== FORCE SUB CHECK ==========
            # Check force subscribe before allowing access to batch files
            is_authorized, error_data = await check_force_sub(client, message)
            
            if not is_authorized:
                # User is not authorized, send force sub message
                await send_force_sub_message(message, error_data, deep_link=deep_link)
                return
            # =====================================
            
            # Handle plain format batch links: get_{channel_id}_{start}_{end}
            if not deep_link.startswith("get_"):
                await message.reply_text("❌ Invalid link format!")
                return
            
            parts = deep_link.split("_")
            
            if len(parts) != 4:
                await message.reply_text("❌ Invalid link format!")
                return
            
            # Batch of messages (supports: text, photos, videos, documents, stickers, GIFs, audio, etc.)
            try:
                channel_id = parts[1]
                start = int(parts[2])
                end = int(parts[3])
            except:
                await message.reply_text("❌ Invalid link!")
                return
            
            # Create list of message IDs to fetch
            if start <= end:
                ids = range(start, end + 1)
            else:
                ids = []
                i = start
                while True:
                    ids.append(i)
                    i -= 1
                    if i < end:
                        break
            
            temp_msg = await message.reply_text("⚡")
            
            try:
                # Get all messages in batch (more efficient, handles all types)
                messages = await get_messages(client, list(ids))
            except:
                await message.reply_text("❌ Something went wrong!")
                return
            
            await temp_msg.delete()
            
            # Send all messages (supports all message types)
            for msg in messages:
                if msg:  # Skip if message is None (deleted)
                    try:
                        await msg.copy(chat_id=message.from_user.id)
                        await asyncio.sleep(0.5)
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                        await msg.copy(chat_id=message.from_user.id)
                    except:
                        continue
            return
            
        except Exception as e:
            logger.error(f"Error processing deep link: {e}", exc_info=True)
            await message.reply_text("❌ Error processing your request!")
            return
    
    # No deep link - show random welcome message
    welcome_text = random.choice(START_MESSAGES)
    await message.reply_text(welcome_text)


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command('help'))
async def help_command(client: Client, message: Message):
    """Handle /help command"""
    help_text = """
<pre><b>📚 SERIES BOT COMMANDS</b></pre>

━━━━━━━━━━━━━━━━━━━━━━

<b>👥 USERS COMMANDS</b>
<i>Available to all users (except banned)</i>

/start - Start the bot and search series
/recent {channel_id} - Send recently added series list to a channel (Admin only)
<b>Send series name</b> - Search for any series directly

━━━━━━━━━━━━━━━━━━━━━━

<b>🔑 AUTH USERS COMMANDS</b>
<i>Available to Auth Users + Admins</i>

<b>Series Management:</b>
/newseries - Create a new series
/editseries - Edit an existing series
/deleteseries - Delete a specific series

<b>Add Poster</b>
/poster - For adding customized poster
Usage: /poster <code>seriesname</code>

<b>Filter Management:</b>
/filter or /add - Add a filter (in groups)
/filters or /viewfilters - View all filters
/del - Delete a filter
/gfilter or /addg - Add global filter
/gfilters or /viewgfilters - View global filters
/delg - Delete global filter

<b>Connection:</b>
/connect - Connect to a group
/connections - View your connections

<b>System:</b>
/ping - Check bot status and response time

━━━━━━━━━━━━━━━━━━━━━━

<b>👑 ADMIN COMMANDS</b>
<i>Available to Admins only</i>

<b>Series Management:</b>
/allseries - View all series in database
/deleteall - Delete all series (requires confirmation)
/help - Show this help message

<b>Auth User Management:</b>
/add_auth - Add an authorized user
/del_auth - Remove an authorized user
/authusers - View all authorized users

<b>User Management:</b>
/ban - Ban a user from the bot
/unban - Unban a user
/banned - View list of banned users
/users - View total user count

<b>Caption:</b>
/filecaption - Set custom caption for files
/viewcaption - View current caption
/delcaption - Reset caption to default 
<b>Support:</b> <code>{filecaption}</code> <code>{filename}</code> <code>{seriesname}</code> 
<code>{language}</code> <code>{season}</code> <code>{episode}</code> <code>{quality}</code>

<b>Broadcast:</b>
/broadcast - Broadcast message to all users (reply to message)
/broadcasttext - Broadcast custom text message
/groupbroadcast - Broadcast to all groups (reply to message)
/groupcount - View total group count
/cleanup - Clean up deleted/blocked users

<b>Chat Management:</b>
/enable - Enable bot in a group
/disable - Disable bot in a group
/chatstatus - Check chat enable/disable status
/leave - Leave a specific chat
/invitelink - Generate chat invite link
/chatinfo - Get detailed chat information

<b>Force Subscribe:</b>
/fsub</code> - View force subscribe settings
/fsub_enable - Enable force subscribe
/fsub_disable - Disable force subscribe
/fsub_channel - Set force subscribe channel
/fsub_message - Set custom force subscribe message
/fsub_stats - View force subscribe statistics
/fsub_clear - Clear force subscribe settings

<b>Filter Management:</b>
/delall - Delete all filters in a group
/delallg - Delete all global filters

<b>Connection:</b>
/disconnect - Disconnect from a group

<b>System:</b>
/restart - Restart the bot
/ping - Check bot status (also available to auth users)

━━━━━━━━━━━━━━━━━━━━━━
"""
    await message.reply_text(help_text)


@Client.on_message(filters.private & auth_filter & filters.command('newseries'))
async def new_series_command(client: Client, message: Message):
    """Handle /newseries command - Search and display results"""
    if len(message.command) < 2:
        await message.reply_text(
            "❌ Please provide a series name!\n\n"
            "<b>Usage:</b> <code>/newseries <name></code>\n"
            "<b>Example:</b> <code>/newseries Peacemaker</code>"
        )
        return
    
    series_name = " ".join(message.command[1:])
    
    # Show searching message
    search_msg = await message.reply_text(f"🔍 Searching for <b>{series_name}</b>...")
    
    try:
        # Search all sources
        results = await metadata_fetcher.search_all(series_name)
        
        if not results:
            await search_msg.edit_text(
                f"❌ No series found for <b>{series_name}</b>\n\n"
                "Try a different search term."
            )
            return
        
        # Build results message with buttons
        text = f"📺 <b>Search Results for '{series_name}'</b>\n\n"
        text += "Select a series to add:\n"
        
        buttons = []
        for result in results:
            button_text = metadata_fetcher.format_button(result)
            buttons.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"selectseries_{result['id']}"
                )
            ])
        
        # Add cancel button
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_search")])
        
        markup = InlineKeyboardMarkup(buttons)
        await search_msg.edit_text(text, reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Error searching series: {e}", exc_info=True)
        await search_msg.edit_text(f"❌ Error searching: {str(e)}")


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command('allseries'))
async def all_series_command(client: Client, message: Message):
    """Handle /allseries command - Shows list in text format"""
    try:
        all_series = await db.get_all_series()
        
        if not all_series:
            await message.reply_text(
                "🔭 No series found!\n\n"
                "Create one using: <code>/newseries <name></code>"
            )
            return
        
        # Find duplicate series names to show year
        title_counts = {}
        for series in all_series:
            title = series.get('title', 'Unknown')
            title_counts[title] = title_counts.get(title, 0) + 1
        
        # Build text list
        text = f"📺 <b>Total Series: {len(all_series)}</b>\n\n"
        
        for idx, series in enumerate(all_series, 1):
            title = series.get('title', 'Unknown')
            year = series.get('year', '')
            
            # Show year only if multiple series with same name exist
            if title_counts.get(title, 0) > 1 and year:
                text += f"{idx}. {title} ({year})\n"
            else:
                text += f"{idx}. {title}\n"
        
        # Check if text exceeds 4000 characters
        if len(text) > 4000:
            # Create HTML file for better viewing
            html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>All Series</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; background: #f5f5f5; }
        h1 { color: #333; text-align: center; }
        .series-list { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .series-item { padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
        .series-item:last-child { border-bottom: none; }
        .series-title { font-weight: bold; color: #333; }
        .series-year { color: #666; margin-left: 5px; }
        .status { padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; }
        .status-published { background: #d4edda; color: #155724; }
        .status-draft { background: #f8d7da; color: #721c24; }
        .total { text-align: center; color: #666; margin-bottom: 20px; font-size: 18px; }
    </style>
</head>
<body>
    <h1>📺 All Series</h1>
    <div class="total">Total: """ + str(len(all_series)) + """ series</div>
    <div class="series-list">
"""
            
            for idx, series in enumerate(all_series, 1):
                title = series.get('title', 'Unknown')
                year = series.get('year', '')
                
                # Show year only if multiple series with same name exist
                if title_counts.get(title, 0) > 1 and year:
                    html_content += f'        <div class="series-item"><span class="series-title">{idx}. {title}</span><span class="series-year">({year})</span></div>\n'
                else:
                    html_content += f'        <div class="series-item"><span class="series-title">{idx}. {title}</span></div>\n'
            
            html_content += """    </div>
</body>
</html>"""
            
            file = io.BytesIO(html_content.encode('utf-8'))
            file.name = "all_series.html"
            
            await message.reply_document(
                document=file,
                caption=f"📺 <b>Total Series: {len(all_series)}</b>\n\nThe list is too long, so here's an HTML file. Download and open in browser."
            )
        else:
            # Send as text message
            await message.reply_text(text)
    
    except Exception as e:
        logger.error(f"Error listing series: {e}", exc_info=True)
        await message.reply_text(f"❌ Error: {str(e)}")


@Client.on_message(filters.private & auth_filter & filters.command('deleteseries'))
async def delete_series_command(client: Client, message: Message):
    """Handle /deleteseries command - Delete by name"""
    if len(message.command) < 2:
        await message.reply_text(
            "❌ Please provide a series name!\n\n"
            "<b>Usage:</b> <code>/deleteseries <name></code>\n"
            "<b>Example:</b> <code>/deleteseries Loki</code>"
        )
        return
    
    series_name = " ".join(message.command[1:])
    
    try:
        # Find series by title (case-insensitive search)
        all_series = await db.get_all_series()
        found_series = None
        
        for series in all_series:
            if series.get('title', '').lower() == series_name.lower():
                found_series = series
                break
        
        if not found_series:
            await message.reply_text(
                f"❌ Series <b>'{series_name}'</b> not found!\n\n"
                "Use <code>/allseries</code> to see all saved series."
            )
            return
        
        # Delete the series
        await db.delete_series(found_series['_id'])
        
        await message.reply_text(
            f"Series <b>'{found_series.get('title', 'Unknown')}'</b> deleted successfully! ✅"
        )
    
    except Exception as e:
        logger.error(f"Error deleting series: {e}", exc_info=True)
        await message.reply_text(f"❌ Error: {str(e)}")


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command('deleteall'))
async def delete_all_command(client: Client, message: Message):
    """Handle /deleteall command"""
    try:
        count = await db.get_series_count()
        
        if count == 0:
            await message.reply_text("🔭 No series found to delete!")
            return
        
        buttons = [
            [
                InlineKeyboardButton("✅ Yes, Delete All", callback_data="confirmdelall"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete")
            ]
        ]
        
        markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(
            f"⚠️ <b>Warning!</b>\n\n"
            f"This will delete <b>{count} series</b> and all their languages, seasons, and qualities.\n\n"
            f"Are you sure?",
            reply_markup=markup
        )
    
    except Exception as e:
        logger.error(f"Error in deleteall command: {e}", exc_info=True)
        await message.reply_text(f"❌ Error: {str(e)}")


@Client.on_message(filters.private & auth_filter & filters.command('editseries'))
async def edit_series_command(client: Client, message: Message):
    """Handle /editseries <series name> command - Open series management and set to draft"""
    if len(message.command) < 2:
        await message.reply_text(
            "❌ Please provide a series name!\n\n"
            "<b>Usage:</b> <code>/editseries <series name></code>\n"
            "<b>Example:</b> <code>/editseries Stranger Things</code>"
        )
        return
    
    series_name = " ".join(message.command[1:])
    
    try:
        # Find series by title (case-insensitive search)
        all_series = await db.get_all_series()
        found_series = None
        
        for series in all_series:
            if series.get('title', '').lower() == series_name.lower():
                found_series = series
                break
        
        if not found_series:
            await message.reply_text(
                f"❌ Series <b>'{series_name}'</b> not found!\n\n"
                "Use <code>/allseries</code> to see all saved series."
            )
            return
        
        # Set series to draft status
        await db.publish_series(found_series['_id'], published=False)
        
        # Show series management view first
        await show_series_main_view(message, found_series['_id'])
        
        # Send popup-style alert as a temporary message
        alert_msg = await message.reply_text(
            f"✏️ Editing {found_series.get('title', 'Unknown')}"
        )
        
        # Delete the alert message after 1 seconds to mimic popup behavior
        await asyncio.sleep(1)
        try:
            await alert_msg.delete()
        except:
            pass
    
    except Exception as e:
        logger.error(f"Error in editseries command: {e}", exc_info=True)
        await message.reply_text(f"❌ Error: {str(e)}")


@Client.on_message(filters.private & filters.user(ADMINS) & filters.command("recent"))
async def recent_command(client: Client, message: Message):
    """
    Handle /recent {channel_id} command (admin only).
    Sends the recently-added series list to the given channel.
    Usage: /recent -1001234567890
    """
    from plugins.recent_list import handle_recent_command

    if len(message.command) < 2:
        await message.reply_text(
            "❌ Please provide a channel ID!\n\n"
            "<b>Usage:</b> <code>/recent {channel_id}</code>\n"
            "<b>Example:</b> <code>/recent -1003780637561</code>"
        )
        return

    channel_arg = message.command[1].strip()
    try:
        channel_id = int(channel_arg)
    except ValueError:
        await message.reply_text("❌ Invalid channel ID! Must be a numeric ID like <code>-1003780637561</code>")
        return

    status_msg = await message.reply_text("⏳ Sending recent list to channel...")
    success = await handle_recent_command(client, channel_id)

    if success:
        await status_msg.edit_text("✅ Recent list sent to channel!")
    else:
        await status_msg.edit_text(
            "❌ Failed to send recent list to channel.\n"
            "Make sure the bot is an admin in that channel."
        )


# ============================================================================
# USER ACCESS - Text-based Series Search
# ============================================================================

@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "newseries", "allseries", "deleteseries", "deleteall", "editseries", "poster", "recent"]) & ~filters.forwarded & ~filters.regex(r't\.me/'), group=0)
async def user_series_search(client: Client, message: Message):
    """Handle user text messages to search for series - WITH SPELL CHECKING AND USER TRACKING"""
    user_id = message.from_user.id
    
    state = state_manager.get_state(user_id)
    
    # If user is in a state (admin adding data), handle that instead
    if state:
        await handle_text_input(client, message)
        return
    
    # Get user's search query
    user_query = message.text.strip()
    
    # ============= USER TRACKING FOR BROADCAST SYSTEM =============
    # MOVED AFTER state check to avoid unnecessary DB calls for admin operations
    # Update user activity when they interact with bot
    if broadcast_db:
        try:
            if not await broadcast_db.is_user_exist(user_id):
                await broadcast_db.add_user(user_id)
            else:
                await broadcast_db.update_last_active(user_id)
        except Exception as e:
            logger.error(f"Error updating user activity: {e}")
    # ==============================================================
    
    try:
        # Get all published series for spell checking
        all_series = await db.get_published_series()
        
        # ============= SPELL CHECKING & SMART MATCHING =============
        should_respond, corrected_query, best_match, confidence = check_series_spelling(
            user_query, 
            all_series
        )
        
        # Ignore irrelevant messages (greetings, random text, etc.)
        if not should_respond:
            logger.info(f"Ignoring non-series query from user {user_id}: {user_query}")
            return
        
        # If we have a high-confidence match (>85%), show it directly
        if best_match and confidence >= 0.85:
            logger.info(f"High confidence match ({confidence:.2%}) for '{user_query}' -> '{best_match.get('title')}'")
            
            # Inform user if spelling was corrected
            if corrected_query.lower() != user_query.lower():
                correction_msg = await message.reply_text(
                    f"🔍 Did you mean: <b>{best_match.get('title')}</b>?"
                )
                await asyncio.sleep(0.5)
            
            await show_user_series_view(message, best_match['_id'], client=client)
            return
        
        # ============= FALLBACK TO SEARCH =============
        # Use corrected query for searching
        search_term = corrected_query.lower() if corrected_query else user_query.lower()
        matching_series = []
        
        for series in all_series:
            title = series.get('title', '').lower()
            if search_term in title:
                matching_series.append(series)
        
        # If we have a fuzzy match but low confidence, include it in results
        if best_match and best_match not in matching_series:
            matching_series.insert(0, best_match)
        
        if not matching_series:
            # Don't send any message to prevent spam
            # Just silently return
            return
        
        # If only one match, show it directly
        if len(matching_series) == 1:
            # Inform user if spelling was corrected
            if corrected_query.lower() != user_query.lower():
                await message.reply_text(
                    f"🔍 Showing results for: <b>{matching_series[0].get('title')}</b>"
                )
                await asyncio.sleep(0.5)
            
            await show_user_series_view(message, matching_series[0]['_id'], client=client)
            return
        
        # Multiple matches - show buttons
        # Show correction message if query was corrected
        if corrected_query.lower() != user_query.lower():
            text = f"🔍 <b>Showing results for: '{corrected_query}'</b>\n\n"
        else:
            text = f"📺 <b>Search Results for '{user_query}'</b>\n\n"
        
        text += "Select a series:\n"
        
        buttons = []
        for series in matching_series[:10]:  # Limit to 10 results
            buttons.append([
                InlineKeyboardButton(
                    series.get('title', 'Unknown'),
                    callback_data=f"userseries_{series['_id']}"
                )
            ])
        
        markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(text, reply_markup=markup)
    
    except Exception as e:
        logger.error(f"Error searching series: {e}", exc_info=True)
        # Silently fail for user searches to avoid spam on non-series messages


# ============================================================================
# USER ACCESS - Group Message Handler
# ============================================================================

@Client.on_message(filters.text & filters.group, group=0)
async def group_series_search(client: Client, message: Message):
    """Handle series search in groups with spell checking - show full series view like in PM"""
    user_query = message.text.strip()
    
    try:
        # Get all published series
        all_series = await db.get_published_series()
        
        # ============= SPELL CHECKING & SMART MATCHING =============
        should_respond, corrected_query, best_match, confidence = check_series_spelling(
            user_query, 
            all_series
        )
        
        # In groups, be more strict - ignore non-series messages
        if not should_respond:
            return
        
        # If high-confidence match (>90% in groups to avoid spam), show it directly
        if best_match and confidence >= 0.90:
            logger.info(f"Group: High confidence match ({confidence:.2%}) for '{user_query}' -> '{best_match.get('title')}'")
            await show_user_series_view(message, best_match['_id'], client=client)
            return
        
        # ============= FALLBACK TO SEARCH =============
        search_term = corrected_query.lower() if corrected_query else user_query.lower()
        matching_series = []
        
        for series in all_series:
            title = series.get('title', '').lower()
            if search_term in title:
                matching_series.append(series)
        
        # Include fuzzy match if available
        if best_match and best_match not in matching_series:
            matching_series.insert(0, best_match)
        
        if not matching_series:
            # Don't respond in groups if no match (avoid spam)
            return
        
        # If only one match, show full series view
        if len(matching_series) == 1:
            await show_user_series_view(message, matching_series[0]['_id'], client=client)
            return
        
        # Multiple matches - show buttons to select
        text = f"📺 <b>Search Results for '{user_query}'</b>\n\n"
        text += "Select a series:\n"
        
        buttons = []
        for series in matching_series[:10]:  # Limit to 10 results
            buttons.append([
                InlineKeyboardButton(
                    series.get('title', 'Unknown'),
                    callback_data=f"userseries_{series['_id']}"
                )
            ])
        
        markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(text, reply_markup=markup)
    
    except Exception as e:
        logger.error(f"Error in group search: {e}", exc_info=True)


# ============================================================================
# USER SERIES VIEW
# ============================================================================

async def show_user_series_view(message_or_query, series_id: str, lang_id: str = None, season_id: str = None, client: Client = None):
    """
    Show series view for regular users (non-admin)
    Displays: Series -> Languages -> Seasons -> Qualities -> Send Batch
    """
    series = await db.get_series(series_id)
    if not series:
        if hasattr(message_or_query, 'answer'):
            await message_or_query.answer("Series not found!", show_alert=True)
        return
    
    # Check if series is published
    if not series.get('published', False):
        if hasattr(message_or_query, 'answer'):
            await message_or_query.answer("This series is not available!", show_alert=True)
        else:
            await message_or_query.reply_text("❌ This series is not available!")
        return
    
    buttons = []
    
    # Determine if we're in a group or PM and get requester user ID
    is_group = False
    requester_id = None
    
    if hasattr(message_or_query, 'message'):
        # This is a callback query
        is_group = message_or_query.message.chat.type != "private"
        requester_id = message_or_query.from_user.id
    elif hasattr(message_or_query, 'chat'):
        # This is a regular message
        is_group = message_or_query.chat.type != "private"
        requester_id = message_or_query.from_user.id
    
    if season_id and lang_id:
        # SEASON VIEW: Show qualities
        lang_data = series.get('languages', {}).get(lang_id, {})
        season_data = lang_data.get('seasons', {}).get(season_id, {})
        
        text = build_series_info_text(series)
        text += f"<pre><b>▪️Language:</b> <code>{lang_data.get('name', 'Unknown')}</code></pre>\n"
        text += f"<pre><b>▪️Season:</b> <code>{season_data.get('name', 'Unknown')}</code></pre>\n"
        
        # Show only published qualities
        quality_buttons = []
        for quality_id_key, quality_data in season_data.get('qualities', {}).items():
            if quality_data.get('published') and quality_data.get('batch_link'):
                # Use callback button for both PM and groups
                quality_buttons.append(
                    InlineKeyboardButton(
                        quality_data.get('name', 'Unknown'),
                        callback_data=f"userquality_{series_id}_{lang_id}_{season_id}_{quality_id_key}"
                    )
                )
        
        # Show published episodes (max 5 per row)
        episode_buttons = []
        for ep_id_key, ep_data in season_data.get('episodes', {}).items():
            # Check if episode has at least one published quality
            has_published = any(
                q.get('published', False) and q.get('file_link')
                for q in ep_data.get('qualities', {}).values()
            )
            if has_published:
                episode_buttons.append(
                    InlineKeyboardButton(
                        ep_data.get('name', 'Unknown'),
                        callback_data=f"userepisode_{series_id}_{lang_id}_{season_id}_{ep_id_key}"
                    )
                )
        
        # Set appropriate caption based on what's available
        if quality_buttons and episode_buttons:
            text += "<i>Select the quality you need...!</i>"
        elif episode_buttons:
            text += "<i>Select an Episode:</i>"
        elif quality_buttons:
            text += "<i>Select the quality you need...!</i>"
        else:
            text += "<i>Select the quality you need...!</i>"
        
        if quality_buttons:
            buttons.extend(group_buttons_in_rows(quality_buttons, 2))
        if episode_buttons:
            buttons.extend(group_buttons_in_rows(episode_buttons, 5))
        
        if not quality_buttons and not episode_buttons:
            text += "\n\n❌ No qualities available yet."
        
        # Back button with requester_id for groups
        if is_group:
            buttons.append([
                InlineKeyboardButton("⪻ Back", callback_data=f"userlang_{series_id}_{lang_id}_{requester_id}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton("⪻ Back", callback_data=f"userlang_{series_id}_{lang_id}")
            ])
    
    elif lang_id:
        # LANGUAGE VIEW: Show seasons
        lang_data = series.get('languages', {}).get(lang_id, {})
        
        text = build_series_info_text(series)
        text += f"<pre><b>▪️Language:</b> <code>{lang_data.get('name', 'Unknown')}</code></pre>\n"
        text += "<i>Available Seasons:</i>"
        
        # Show seasons that have at least one published quality or episode
        season_buttons = []
        for season_id_key, season_data in lang_data.get('seasons', {}).items():
            # Check if season has published batch qualities
            has_published = any(
                q.get('published', False) and q.get('batch_link')
                for q in season_data.get('qualities', {}).values()
            )
            # Also check if season has published episode qualities
            if not has_published:
                for ep_data in season_data.get('episodes', {}).values():
                    if any(q.get('published', False) and q.get('file_link') for q in ep_data.get('qualities', {}).values()):
                        has_published = True
                        break
            if has_published:
                # Add requester_id to callback data for groups
                if is_group:
                    callback_data = f"userseason_{series_id}_{lang_id}_{season_id_key}_{requester_id}"
                else:
                    callback_data = f"userseason_{series_id}_{lang_id}_{season_id_key}"
                
                season_buttons.append(
                    InlineKeyboardButton(
                        season_data.get('name', 'Unknown'),
                        callback_data=callback_data
                    )
                )
        
        if season_buttons:
            buttons.extend(group_buttons_in_rows(season_buttons, 3))
        else:
            text += "\n\n❌ No seasons available yet."
        
       # Back button with requester_id for groups
        if is_group:
            buttons.append([
                InlineKeyboardButton("⪻ Back", callback_data=f"userseries_{series_id}_{requester_id}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton("⪻ Back", callback_data=f"userseries_{series_id}")
            ])
    
    else:
        # SERIES VIEW: Show languages
        text = build_series_info_text(series)
        text += "\n<i>Available Languages:</i>"
        
        # Show only languages that have published content (batch OR episode files)
        lang_buttons = []
        for lang_id_key, lang_data in series.get('languages', {}).items():
            has_published = False
            for season_data in lang_data.get('seasons', {}).values():
                # Check season-level batch qualities
                if any(q.get('published', False) and q.get('batch_link')
                       for q in season_data.get('qualities', {}).values()):
                    has_published = True
                    break
                # Check episode-level file qualities
                for ep_data in season_data.get('episodes', {}).values():
                    if any(q.get('published', False) and q.get('file_link')
                           for q in ep_data.get('qualities', {}).values()):
                        has_published = True
                        break
                if has_published:
                    break
            if has_published:
                # Add requester_id to callback data for groups
                if is_group:
                    callback_data = f"userlang_{series_id}_{lang_id_key}_{requester_id}"
                else:
                    callback_data = f"userlang_{series_id}_{lang_id_key}"
                
                lang_buttons.append(
                    InlineKeyboardButton(
                        lang_data.get('name', 'Unknown'),
                        callback_data=callback_data
                    )
                )
        
        if lang_buttons:
            buttons.extend(group_buttons_in_rows(lang_buttons, 2))
        else:
            text += "\n❌ No languages available yet."
    
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    
    # Send with poster if available
    poster_url = series.get('poster_url', '')
    
    if hasattr(message_or_query, 'message'):
        # This is a callback query
        msg = message_or_query.message
        try:
            if poster_url:
                if msg.photo:
                    from pyrogram.types import InputMediaPhoto
                    try:
                        await msg.edit_media(
                            media=InputMediaPhoto(media=poster_url, caption=text),
                            reply_markup=markup
                        )
                    except Exception as media_err:
                        logger.warning(f"Failed to use poster URL (edit_media): {media_err}")
                        await msg.delete()
                        await msg.reply_text(text, reply_markup=markup)
                else:
                    try:
                        await msg.delete()
                        await msg.reply_photo(
                            photo=poster_url,
                            caption=text,
                            reply_markup=markup
                        )
                    except Exception as photo_err:
                        logger.warning(f"Failed to use poster URL (reply_photo): {photo_err}")
                        await msg.reply_text(text, reply_markup=markup)
            else:
                if msg.photo:
                    await msg.delete()
                    await msg.reply_text(text, reply_markup=markup)
                else:
                    await msg.edit_text(text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Error updating message: {e}")
            await msg.reply_text(text, reply_markup=markup)
    else:
        # This is a regular message
        if poster_url:
            try:
                await message_or_query.reply_photo(
                    photo=poster_url,
                    caption=text,
                    reply_markup=markup
                )
            except Exception as photo_err:
                logger.warning(f"Failed to use poster URL (reply_photo): {photo_err}")
                await message_or_query.reply_text(text, reply_markup=markup)
        else:
            await message_or_query.reply_text(text, reply_markup=markup)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def group_buttons_in_rows(buttons, buttons_per_row):
    """Group buttons into rows"""
    return [buttons[i:i + buttons_per_row] for i in range(0, len(buttons), buttons_per_row)]


def build_series_info_text(series):
    """Build series information text"""
    text = f"○ <b>Title:</b> <code>{series.get('title', 'Unknown Series')}</code>\n"
    
    if series.get('year'):
        text += f"○ <b>Released On:</b> <code>{series['year']}</code>\n"
    
    if series.get('genre'):
        text += f"○ <b>Genre:</b> <code>{series['genre']}</code>\n"
    
    if series.get('rating') and series['rating'] not in ['', '0', 'N/A']:
        text += f"○ <b>Rating:</b> <code>{series['rating']}</code>\n"
    
    return text


# ============================================================================
# MAIN SERIES VIEW (ADMIN)
# ============================================================================

async def show_series_main_view(message_or_query, series_id: str, lang_id: str = None, season_id: str = None):
    """
    Main function to show series with dynamic navigation (ADMIN VIEW)
    
    Args:
        message_or_query: Can be Message or CallbackQuery
        series_id: The series ID
        lang_id: Optional language ID to show language view
        season_id: Optional season ID to show season view
    """
    series = await db.get_series(series_id)
    if not series:
        if hasattr(message_or_query, 'answer'):
            await message_or_query.answer("Series not found!", show_alert=True)
        return
    
    buttons = []
    
    if season_id and lang_id:
        # SEASON VIEW: Show qualities
        lang_data = series.get('languages', {}).get(lang_id, {})
        season_data = lang_data.get('seasons', {}).get(season_id, {})
        
        text = build_series_info_text(series)
        text += f"<pre><b>▪️Language:</b> <code>{lang_data.get('name', 'Unknown')}</code></pre>\n"
        text += f"<pre><b>▪️Season:</b> <code>{season_data.get('name', 'Unknown')}</code></pre>\n"
        text += "<b>Select a quality or add new:</b>"
        
        # Show qualities (no status indicator)
        if season_data.get('qualities'):
            quality_buttons = []
            for quality_id_key, quality_data in season_data['qualities'].items():
                quality_name = quality_data.get('name', 'Unknown')
                quality_buttons.append(
                    InlineKeyboardButton(
                        quality_name,
                        callback_data=f"quality_{series_id}_{lang_id}_{season_id}_{quality_id_key}"
                    )
                )
            buttons.extend(group_buttons_in_rows(quality_buttons, 2))

        # Show episodes (max 5 per row)
        if season_data.get('episodes'):
            episode_buttons = []
            for ep_id_key, ep_data in season_data['episodes'].items():
                episode_buttons.append(
                    InlineKeyboardButton(
                        ep_data.get('name', 'Unknown'),
                        callback_data=f"episode_{series_id}_{lang_id}_{season_id}_{ep_id_key}"
                    )
                )
            buttons.extend(group_buttons_in_rows(episode_buttons, 5))
        
        # Action buttons
        buttons.extend([
            [InlineKeyboardButton("➕ Add Quality", callback_data=f"addquality_{series_id}_{lang_id}_{season_id}")],
            [
                InlineKeyboardButton("📺 Add Episode", callback_data=f"addepisode_{series_id}_{lang_id}_{season_id}"),
                InlineKeyboardButton("🗑 Clear Episodes", callback_data=f"clearepisodes_{series_id}_{lang_id}_{season_id}")
            ],
            [InlineKeyboardButton("🗑️ Delete Season", callback_data=f"deleteseason_{series_id}_{lang_id}_{season_id}")],
            [InlineKeyboardButton("⪻ Back", callback_data=f"lang_{series_id}_{lang_id}")]
        ])
    
    elif lang_id:
        # LANGUAGE VIEW: Show seasons
        lang_data = series.get('languages', {}).get(lang_id, {})
        
        text = build_series_info_text(series)
        text += f"<pre><b>▪️Language:</b> <code>{lang_data.get('name', 'Unknown')}</code></pre>\n"
        text += "<b>Select a season or add new:</b>"
        
        # Show seasons
        if lang_data.get('seasons'):
            season_buttons = []
            for season_id_key, season_data in lang_data['seasons'].items():
                season_buttons.append(
                    InlineKeyboardButton(
                        season_data.get('name', 'Unknown'),
                        callback_data=f"season_{series_id}_{lang_id}_{season_id_key}"
                    )
                )
            buttons.extend(group_buttons_in_rows(season_buttons, 3))
        
        # Action buttons
        buttons.extend([
            [InlineKeyboardButton("➕ Add Season", callback_data=f"addseason_{series_id}_{lang_id}")],
            [InlineKeyboardButton("🗑️ Delete Language", callback_data=f"deletelang_{series_id}_{lang_id}")],
            [InlineKeyboardButton("⪻ Back", callback_data=f"series_{series_id}")]
        ])
    
    else:
        # SERIES VIEW: Show languages
        text = build_series_info_text(series)
        
        # Show published status
        is_published = series.get('published', False)
        text += f"\n<b>Status:</b> {'🟢 Published' if is_published else '🔴 Draft'}\n"
        
        # Show languages (2 per row)
        if series.get('languages'):
            lang_buttons = []
            for lang_id_key, lang_data in series['languages'].items():
                lang_buttons.append(
                    InlineKeyboardButton(
                        lang_data.get('name', 'Unknown'),
                        callback_data=f"lang_{series_id}_{lang_id_key}"
                    )
                )
            buttons.extend(group_buttons_in_rows(lang_buttons, 2))
        
        # Main action buttons
        buttons.extend([
            [InlineKeyboardButton("➕ Add Language", callback_data=f"addlang_{series_id}")],
            [
                InlineKeyboardButton("🔄 Update Poster", callback_data=f"update_poster_{series_id}"),
                InlineKeyboardButton("✏️ Edit Details", callback_data=f"edit_details_{series_id}")
            ],
            [
                InlineKeyboardButton("🗑️ Delete Series", callback_data=f"delete_series_{series_id}"),
                InlineKeyboardButton("🟢 Publish" if not is_published else "🔴 Unpublish", 
                                   callback_data=f"publish_series_{series_id}")
            ]
        ])
    
    markup = InlineKeyboardMarkup(buttons)
    
    # Send with poster if available
    poster_url = series.get('poster_url', '')
    
    if hasattr(message_or_query, 'message'):
        # This is a callback query
        msg = message_or_query.message
        try:
            if poster_url:
                if msg.photo:
                    from pyrogram.types import InputMediaPhoto
                    try:
                        await msg.edit_media(
                            media=InputMediaPhoto(media=poster_url, caption=text),
                            reply_markup=markup
                        )
                    except Exception as media_err:
                        logger.warning(f"Failed to use poster URL (edit_media): {media_err}")
                        await msg.delete()
                        await msg.reply_text(text, reply_markup=markup)
                else:
                    try:
                        await msg.delete()
                        await msg.reply_photo(
                            photo=poster_url,
                            caption=text,
                            reply_markup=markup
                        )
                    except Exception as photo_err:
                        logger.warning(f"Failed to use poster URL (reply_photo): {photo_err}")
                        await msg.reply_text(text, reply_markup=markup)
            else:
                if msg.photo:
                    await msg.delete()
                    await msg.reply_text(text, reply_markup=markup)
                else:
                    await msg.edit_text(text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Error updating message: {e}")
            await msg.reply_text(text, reply_markup=markup)
    else:
        # This is a regular message
        if poster_url:
            try:
                await message_or_query.reply_photo(
                    photo=poster_url,
                    caption=text,
                    reply_markup=markup
                )
            except Exception as photo_err:
                logger.warning(f"Failed to use poster URL (reply_photo): {photo_err}")
                await message_or_query.reply_text(text, reply_markup=markup)
        else:
            await message_or_query.reply_text(text, reply_markup=markup)


# ============================================================================
# ACTION HANDLERS - With ReplyKeyboardMarkup support
# ============================================================================

async def handle_add_language(client: Client, callback_query: CallbackQuery, series_id: str):
    """Handle adding a new language with ReplyKeyboardMarkup"""
    user_id = callback_query.from_user.id
    
    state_manager.set_state(
        user_id=user_id,
        action='adding_language',
        series_id=series_id,
        message_id=callback_query.message.id
    )
    
    # Create language selection keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["Malayalam", "Hindi", "English"],
            ["Tamil", "Telugu", "Kannada"],
            ["Korean", "Chinese", "Japanese"]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback_query.message.reply_text(
        "Please select or send the language name:",
        reply_markup=keyboard
    )
    await callback_query.answer()


async def handle_add_season(client: Client, callback_query: CallbackQuery, series_id: str, lang_id: str):
    """Handle adding a new season with ReplyKeyboardMarkup"""
    user_id = callback_query.from_user.id
    
    state_manager.set_state(
        user_id=user_id,
        action='adding_season',
        series_id=series_id,
        lang_id=lang_id,
        message_id=callback_query.message.id
    )
    
    # Create season selection keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["Season 1", "Season 2", "Season 3"],
            ["Season 4", "Season 5", "Season 6"],
            ["Season 7", "Season 8", "Season 9"]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback_query.message.reply_text(
        "Please select or send the season name:",
        reply_markup=keyboard
    )
    await callback_query.answer()


async def handle_add_quality(client: Client, callback_query: CallbackQuery, series_id: str, lang_id: str, season_id: str):
    """Handle adding a new quality with ReplyKeyboardMarkup"""
    user_id = callback_query.from_user.id
    
    state_manager.set_state(
        user_id=user_id,
        action='adding_quality',
        series_id=series_id,
        lang_id=lang_id,
        season_id=season_id,
        message_id=callback_query.message.id
    )
    
    # Create quality selection keyboard
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["720p.Av1", "720p.H.264", "720p.H.265"],
            ["1080p.Av1", "1080p.H.264", "1080p.H.265"],
            ["480p", "2160p.HDR", "2160p.Atmos"]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback_query.message.reply_text(
        "Please select or send the quality name:",
        reply_markup=keyboard
    )
    await callback_query.answer()


async def handle_add_episode(client, callback_query, series_id, lang_id, season_id):
    """Handle adding a new episode"""
    user_id = callback_query.from_user.id
    state_manager.set_state(
        user_id=user_id,
        action='adding_episode',
        series_id=series_id,
        lang_id=lang_id,
        season_id=season_id,
        message_id=callback_query.message.id
    )
    await callback_query.message.reply_text(
        "📺 Send the episode name (Example: <code>E01</code>):"
    )
    await callback_query.answer()


async def show_episode_admin_view(message_or_query, series_id, lang_id, season_id, episode_id):
    """Show admin view for a specific episode"""
    series = await db.get_series(series_id)
    if not series:
        if hasattr(message_or_query, 'answer'):
            await message_or_query.answer("Series not found!", show_alert=True)
        return

    lang_data = series.get('languages', {}).get(lang_id, {})
    season_data = lang_data.get('seasons', {}).get(season_id, {})
    episode_data = season_data.get('episodes', {}).get(episode_id, {})

    text = build_series_info_text(series)
    text += f"<pre><b>\u25aa\ufe0fLanguage:</b> <code>{lang_data.get('name', 'Unknown')}</code></pre>\n"
    text += f"<pre><b>\u25aa\ufe0fSeason:</b> <code>{season_data.get('name', 'Unknown')}</code></pre>\n"
    text += f"<pre><b>\u25aa\ufe0fEpisode:</b> <code>{episode_data.get('name', 'Unknown')}</code></pre>\n"
    text += "<b>Select a quality or add new:</b>"

    buttons = []

    if episode_data.get('qualities'):
        quality_buttons = []
        for quality_id_key, quality_data in episode_data['qualities'].items():
            quality_name = quality_data.get('name', 'Unknown')
            quality_buttons.append(
                InlineKeyboardButton(
                    quality_name,
                    callback_data=f"epquality_{series_id}_{lang_id}_{season_id}_{episode_id}_{quality_id_key}"
                )
            )
        buttons.extend(group_buttons_in_rows(quality_buttons, 2))

    buttons.extend([
        [InlineKeyboardButton("\u2795 Add Quality", callback_data=f"addepquality_{series_id}_{lang_id}_{season_id}_{episode_id}")],
        [InlineKeyboardButton("\U0001f5d1\ufe0f Delete Episode", callback_data=f"deleteepisode_{series_id}_{lang_id}_{season_id}_{episode_id}")],
        [InlineKeyboardButton("\u2aab Back", callback_data=f"season_{series_id}_{lang_id}_{season_id}")]
    ])

    markup = InlineKeyboardMarkup(buttons)
    poster_url = series.get('poster_url', '')

    if hasattr(message_or_query, 'message'):
        msg = message_or_query.message
        try:
            if poster_url and msg.photo:
                from pyrogram.types import InputMediaPhoto
                await msg.edit_media(
                    media=InputMediaPhoto(media=poster_url, caption=text),
                    reply_markup=markup
                )
            elif msg.photo:
                await msg.delete()
                await msg.reply_text(text, reply_markup=markup)
            else:
                await msg.edit_text(text, reply_markup=markup)
        except Exception as e:
            logger.error(f"Error updating episode view: {e}")
            await msg.reply_text(text, reply_markup=markup)
    else:
        if poster_url:
            try:
                await message_or_query.reply_photo(photo=poster_url, caption=text, reply_markup=markup)
            except:
                await message_or_query.reply_text(text, reply_markup=markup)
        else:
            await message_or_query.reply_text(text, reply_markup=markup)


async def handle_add_episode_quality(client, callback_query, series_id, lang_id, season_id, episode_id):
    """Handle adding quality for a specific episode"""
    user_id = callback_query.from_user.id
    state_manager.set_state(
        user_id=user_id,
        action='adding_episode_quality',
        series_id=series_id,
        lang_id=lang_id,
        season_id=season_id,
        episode_id=episode_id,
        message_id=callback_query.message.id
    )
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["720p.Av1", "720p.H.264", "720p.H.265"],
            ["1080p.Av1", "1080p.H.264", "1080p.H.265"],
            ["480p", "2160p.HDR", "2160p.Atmos"]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await callback_query.message.reply_text(
        "Please select or send the quality name:",
        reply_markup=keyboard
    )
    await callback_query.answer()


async def handle_episode_quality_click(client, callback_query, series_id, lang_id, season_id, episode_id, quality_id):
    """Handle when admin clicks on episode quality to add a file"""
    user_id = callback_query.from_user.id
    if not MAIN_DB_CHANNEL:
        await callback_query.answer("\u26a0\ufe0f Main DB Channel is not configured!", show_alert=True)
        return

    series = await db.get_series(series_id)
    episode_data = series.get('languages', {}).get(lang_id, {}).get('seasons', {}).get(season_id, {}).get('episodes', {}).get(episode_id, {})
    quality_data = episode_data.get('qualities', {}).get(quality_id, {})
    episode_name = episode_data.get('name', 'Episode')
    quality_name = quality_data.get('name', 'Quality')

    state_manager.set_state(
        user_id=user_id,
        action='adding_episode_file',
        series_id=series_id,
        lang_id=lang_id,
        season_id=season_id,
        episode_id=episode_id,
        quality_id=quality_id,
        message_id=callback_query.message.id
    )
    await callback_query.message.reply_text(
        f"\U0001f4e4 Send the <b>{episode_name}</b> file for quality <b>{quality_name}</b>:"
    )
    await callback_query.answer()


async def handle_update_poster(client: Client, callback_query: CallbackQuery, series_id: str):
    """Handle updating series poster"""
    user_id = callback_query.from_user.id
    
    state_manager.set_state(
        user_id=user_id,
        action='updating_poster',
        series_id=series_id,
        message_id=callback_query.message.id
    )
    
    await callback_query.message.reply_text(
        "📸 Please send the new poster image for this series."
    )
    await callback_query.answer()


async def handle_edit_details(client: Client, callback_query: CallbackQuery, series_id: str):
    """Handle editing series details"""
    user_id = callback_query.from_user.id
    
    state_manager.set_state(
        user_id=user_id,
        action='editing_details',
        series_id=series_id,
        message_id=callback_query.message.id
    )
    
    await callback_query.message.reply_text(
        "✏️ Please send the new series details in the following format:\n\n"
        "<b>Example:</b>\n"
        "○ Title: His & Hers\n"
        "○ Released On: 2026-2026\n"
        "○ Genre: Crime, Drama, Mystery, Thriller\n"
        "○ Rating: 7.2"
    )
    await callback_query.answer()


async def handle_quality_click(client: Client, callback_query: CallbackQuery, series_id: str, lang_id: str, season_id: str, quality_id: str):
    """Handle when user clicks on a quality button - Start new batch process with Main DB"""
    user_id = callback_query.from_user.id
    
    # Check if MAIN_DB_CHANNEL is configured
    if not MAIN_DB_CHANNEL:
        await callback_query.answer(
            "⚠️ Main DB Channel is not configured! Please set MAIN_DB_CHANNEL in info.py",
            show_alert=True
        )
        return
    
    # Set state for batch upload
    state_manager.set_state(
        user_id=user_id,
        action='adding_batch_first_new',  # NEW workflow
        series_id=series_id,
        lang_id=lang_id,
        season_id=season_id,
        quality_id=quality_id,
        message_id=callback_query.message.id
    )
    
    await callback_query.message.reply_text(
        "Add me to the channel as admin and forward the <b>First Message</b> from your channel (with forward tag)..📤"
    )
    await callback_query.answer()


async def handle_text_input(client: Client, message: Message):
    """Handle text input for custom entries"""
    user_id = message.from_user.id
    state = state_manager.get_state(user_id)
    
    if not state:
        return
    
    text = message.text.strip()
    
    try:
        if state.action == 'adding_language':
            lang_id = str(uuid.uuid4())[:8]
            await db.add_language(state.series_id, lang_id, text)
            
            # Delete user's input message
            try:
                await message.delete()
            except:
                pass
            
            # Delete the prompt message
            try:
                await client.delete_messages(message.chat.id, message.id - 1)
            except:
                pass
            
            # Remove the keyboard
            await message.reply_text(
                f"Language <b>{text}</b> added! ✅",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Update the main message to show the series view
            try:
                main_msg = await client.get_messages(message.chat.id, state.message_id)
                class FakeQuery:
                    def __init__(self, msg):
                        self.message = msg
                await show_series_main_view(FakeQuery(main_msg), state.series_id)
            except Exception as e:
                logger.error(f"Error updating main message: {e}")
            
            state_manager.clear_state(user_id)
        
        elif state.action == 'adding_season':
            season_id = str(uuid.uuid4())[:8]
            await db.add_season(state.series_id, state.lang_id, season_id, text)
            
            # Delete user's input message
            try:
                await message.delete()
            except:
                pass
            
            # Delete the prompt message
            try:
                await client.delete_messages(message.chat.id, message.id - 1)
            except:
                pass
            
            # Remove the keyboard
            await message.reply_text(
                f"Season <b>{text}</b> added! ✅",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Update the main message to show the language view
            try:
                main_msg = await client.get_messages(message.chat.id, state.message_id)
                class FakeQuery:
                    def __init__(self, msg):
                        self.message = msg
                await show_series_main_view(FakeQuery(main_msg), state.series_id, state.lang_id)
            except Exception as e:
                logger.error(f"Error updating main message: {e}")
            
            state_manager.clear_state(user_id)
        
        elif state.action == 'adding_quality':
            quality_id = str(uuid.uuid4())[:8]
            await db.add_quality(state.series_id, state.lang_id, state.season_id, quality_id, text)
            
            # Delete user's input message
            try:
                await message.delete()
            except:
                pass
            
            # Delete the prompt message
            try:
                await client.delete_messages(message.chat.id, message.id - 1)
            except:
                pass
            
            # Remove the keyboard
            await message.reply_text(
                f"Quality <b>{text}</b> added! ✅",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Update the main message to show the season view
            try:
                main_msg = await client.get_messages(message.chat.id, state.message_id)
                class FakeQuery:
                    def __init__(self, msg):
                        self.message = msg
                await show_series_main_view(FakeQuery(main_msg), state.series_id, state.lang_id, state.season_id)
            except Exception as e:
                logger.error(f"Error updating main message: {e}")
            
            state_manager.clear_state(user_id)
        
        elif state.action == 'adding_episode':
            episode_id = str(uuid.uuid4())[:8]
            await db.add_episode(state.series_id, state.lang_id, state.season_id, episode_id, text)
            
            try:
                await message.delete()
            except:
                pass
            try:
                await client.delete_messages(message.chat.id, message.id - 1)
            except:
                pass
            
            await message.reply_text(
                f"Episode <b>{text}</b> added! ✅",
                reply_markup=ReplyKeyboardRemove()
            )
            
            try:
                main_msg = await client.get_messages(message.chat.id, state.message_id)
                class FakeQuery:
                    def __init__(self, msg):
                        self.message = msg
                await show_series_main_view(FakeQuery(main_msg), state.series_id, state.lang_id, state.season_id)
            except Exception as e:
                logger.error(f"Error updating main message: {e}")
            
            state_manager.clear_state(user_id)
        
        elif state.action == 'adding_episode_quality':
            quality_id = str(uuid.uuid4())[:8]
            await db.add_episode_quality(state.series_id, state.lang_id, state.season_id, state.episode_id, quality_id, text)
            
            try:
                await message.delete()
            except:
                pass
            try:
                await client.delete_messages(message.chat.id, message.id - 1)
            except:
                pass
            
            await message.reply_text(
                f"Quality <b>{text}</b> added! ✅",
                reply_markup=ReplyKeyboardRemove()
            )
            
            try:
                main_msg = await client.get_messages(message.chat.id, state.message_id)
                class FakeQuery:
                    def __init__(self, msg):
                        self.message = msg
                await show_episode_admin_view(FakeQuery(main_msg), state.series_id, state.lang_id, state.season_id, state.episode_id)
            except Exception as e:
                logger.error(f"Error updating main message: {e}")
            
            state_manager.clear_state(user_id)
        
        elif state.action == 'editing_details':
            # Parse the details from text
            details = {}
            for line in text.split('\n'):
                line = line.strip()
                if ':' in line:
                    # Remove the bullet point if present
                    line = line.lstrip('○').strip()
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if 'title' in key:
                        details['title'] = value
                    elif 'released' in key or 'year' in key:
                        details['year'] = value
                    elif 'genre' in key:
                        details['genre'] = value
                    elif 'rating' in key:
                        details['rating'] = value
            
            # Update the series details
            if details:
                await db.update_series_details(state.series_id, details)
                
                # Delete user's input message
                try:
                    await message.delete()
                except:
                    pass
                
                # Delete the prompt message
                try:
                    await client.delete_messages(message.chat.id, message.id - 1)
                except:
                    pass
                
                await message.reply_text("Series details updated successfully! ✅")
                
                # Update the main message to show the updated series view
                try:
                    main_msg = await client.get_messages(message.chat.id, state.message_id)
                    class FakeQuery:
                        def __init__(self, msg):
                            self.message = msg
                    await show_series_main_view(FakeQuery(main_msg), state.series_id)
                except Exception as e:
                    logger.error(f"Error updating main message: {e}")
            else:
                await message.reply_text("❌ Invalid format! Please try again.")
            
            state_manager.clear_state(user_id)
    
    except Exception as e:
        logger.error(f"Error handling text input: {e}", exc_info=True)
        await message.reply_text(f"❌ Error: {str(e)}", reply_markup=ReplyKeyboardRemove())
        state_manager.clear_state(user_id)


async def handle_photo_input(client: Client, message: Message):
    """Handle photo input for poster update"""
    user_id = message.from_user.id
    state = state_manager.get_state(user_id)
    
    if not state or state.action != 'updating_poster':
        return
    
    try:
        # Download the photo
        photo_path = await message.download()
        
        # Show uploading message
        status_msg = await message.reply_text("Uploading poster to ImgBB...⏳")
        
        # Upload to ImgBB
        poster_url = await upload_to_imgbb(photo_path)
        
        if poster_url:
            # Update the series poster
            await db.update_series_poster(state.series_id, poster_url)
            
            # Delete the downloaded file
            try:
                import os
                os.remove(photo_path)
            except:
                pass
            
            # Delete user's photo message
            try:
                await message.delete()
            except:
                pass
            
            # Delete the prompt message
            try:
                await client.delete_messages(message.chat.id, message.id - 1)
            except:
                pass
            
            await status_msg.edit_text("Poster updated successfully! ✅")
            
            # Update the main message to show the updated series view
            try:
                main_msg = await client.get_messages(message.chat.id, state.message_id)
                class FakeQuery:
                    def __init__(self, msg):
                        self.message = msg
                await show_series_main_view(FakeQuery(main_msg), state.series_id)
            except Exception as e:
                logger.error(f"Error updating main message: {e}")
        else:
            await status_msg.edit_text("❌ Failed to upload poster! Please try again.")
        
        state_manager.clear_state(user_id)
    
    except Exception as e:
        logger.error(f"Error handling photo input: {e}", exc_info=True)
        await message.reply_text(f"❌ Error: {str(e)}")
        state_manager.clear_state(user_id)


async def handle_forwarded_or_link(client: Client, message: Message):
    """Handle forwarded messages for NEW batch system with Main DB"""
    user_id = message.from_user.id
    state = state_manager.get_state(user_id)
    
    if not state:
        return
    
    try:
        # NEW WORKFLOW: adding_batch_first_new and adding_batch_last_new
        if state.action == 'adding_batch_first_new':
            # Verify it's a forwarded message
            if not message.forward_from_chat:
                await message.reply_text(
                    "❌ Please forward a message from your channel (with forward tag)!",
                    quote=True
                )
                return
            
            # Get source channel ID and message ID
            source_channel_id = message.forward_from_chat.id
            source_first_msg_id = message.forward_from_message_id
            
            # Store source channel info and first message ID
            state_manager.set_state(
                user_id=user_id,
                action='adding_batch_last_new',
                series_id=state.series_id,
                lang_id=state.lang_id,
                season_id=state.season_id,
                quality_id=state.quality_id,
                message_id=state.message_id,
                first_msg_id=source_first_msg_id
            )
            
            # Store source channel ID in state (we'll use a temporary dict)
            if not hasattr(state_manager, 'temp_data'):
                state_manager.temp_data = {}
            state_manager.temp_data[user_id] = {'source_channel_id': source_channel_id}
            
            # Delete the forwarded message
            try:
                await message.delete()
            except:
                pass
            
            # Delete the prompt message
            try:
                await client.delete_messages(message.chat.id, message.id - 1)
            except:
                pass
            
            # Ask for last message
            await message.reply_text(
                "Forward the <b>Last Message</b> from the same channel (with forward tag)..📤"
            )
        
        elif state.action == 'adding_batch_last_new':
            # Verify it's a forwarded message
            if not message.forward_from_chat:
                await message.reply_text(
                    "❌ Please forward a message from your channel (with forward tag)!",
                    quote=True
                )
                return
            
            # Get source channel ID and last message ID
            source_channel_id = message.forward_from_chat.id
            source_last_msg_id = message.forward_from_message_id
            source_first_msg_id = state.first_msg_id
            
            # Verify it's from the same channel
            temp_data = getattr(state_manager, 'temp_data', {}).get(user_id, {})
            if source_channel_id != temp_data.get('source_channel_id'):
                await message.reply_text(
                    "❌ Error: Last message must be from the same channel as the first message!",
                    quote=True
                )
                return
            
            # Delete the forwarded message
            try:
                await message.delete()
            except:
                pass
            
            # Delete the prompt message
            try:
                await client.delete_messages(message.chat.id, message.id - 1)
            except:
                pass
            
            # Show processing message
            processing_msg = await message.reply_text(
                "<b>Processing batch...⏳</b>"
            )
            
            try:
                # Step 1: Get all messages from source channel (UNLIMITED)
                message_ids = list(range(source_first_msg_id, source_last_msg_id + 1))
                total_msgs = len(message_ids)
                
                await processing_msg.edit_text(
                    f"<b>Fetching {total_msgs} messages...⏳</b>"
                )
                
                # Get messages from source channel in batches of 200
                source_messages = []
                batch_size = 200
                
                for i in range(0, len(message_ids), batch_size):
                    batch_ids = message_ids[i:i + batch_size]
                    
                    try:
                        # Fetch batch with FloodWait handling
                        msgs = await client.get_messages(source_channel_id, batch_ids)
                        
                        # Filter out None messages
                        if isinstance(msgs, list):
                            source_messages.extend([msg for msg in msgs if msg is not None])
                        elif msgs is not None:
                            source_messages.append(msgs)
                            
                    except FloodWait as e:
                        logger.warning(f"FloodWait: Waiting {e.value} seconds while fetching...")
                        await processing_msg.edit_text(
                            f"<b>FloodWait: Waiting {e.value} seconds...⏳</b>\n"
                            f"Fetched: {len(source_messages)}/{total_msgs}"
                        )
                        await asyncio.sleep(e.value)
                        
                        # Retry after waiting
                        try:
                            msgs = await client.get_messages(source_channel_id, batch_ids)
                            if isinstance(msgs, list):
                                source_messages.extend([msg for msg in msgs if msg is not None])
                            elif msgs is not None:
                                source_messages.append(msgs)
                        except Exception as e:
                            logger.error(f"Error retrying batch fetch: {e}")
                            
                    except Exception as e:
                        logger.error(f"Error fetching batch: {e}")
                
                if not source_messages:
                    await processing_msg.edit_text("❌ Error: Could not fetch messages from source channel!")
                    state_manager.clear_state(user_id)
                    return
                
                await processing_msg.edit_text(
                    f"<b>Copying {len(source_messages)} messages to Main DB...⏳</b>"
                )
                
                # Step 2: Copy messages to Main DB with custom captions (UNLIMITED with FloodWait)
                main_db_message_ids = []
                copied_count = 0
                
                for idx, msg in enumerate(source_messages, 1):
                    try:
                        # Apply custom caption using caption_handler
                        new_caption = None
                        if msg.document or msg.video or msg.audio:
                            # Get file name
                            file_name = "Unknown"
                            if msg.document:
                                file_name = msg.document.file_name or "Unknown"
                            elif msg.video:
                                file_name = msg.video.file_name or "video.mp4"
                            elif msg.audio:
                                file_name = msg.audio.file_name or "audio.mp3"
                            
                            # Get original caption
                            original_caption = msg.caption or ""
                            
                            # Get user's caption template (or use CUSTOM_FILE_CAPTION from info.py)
                            caption_template = await get_caption_template(user_id)
                            if caption_template == "{filename}":  # Default template
                                # Use CUSTOM_FILE_CAPTION from info.py if no user template set
                                caption_template = CUSTOM_FILE_CAPTION
                            
                            # Get series data from state for more accurate info
                            series_data = None
                            if state:
                                # Get series info from database
                                series_doc = await db.get_series(state.series_id)
                                if series_doc:
                                    # Extract series name, language, and quality from state
                                    series_name = series_doc.get('title', '')
                                    
                                    # Get language name
                                    language = ''
                                    if state.lang_id and state.lang_id in series_doc.get('languages', {}):
                                        language = series_doc['languages'][state.lang_id].get('name', '')
                                    
                                    # Get quality name
                                    quality = ''
                                    if state.season_id and state.quality_id:
                                        season_data = series_doc.get('languages', {}).get(state.lang_id, {}).get('seasons', {}).get(state.season_id, {})
                                        quality_data = season_data.get('qualities', {}).get(state.quality_id, {})
                                        quality = quality_data.get('name', '')
                                    
                                    series_data = {
                                        'series_name': series_name,
                                        'language': language,
                                        'quality': quality
                                    }
                            
                            # Format caption with all variables
                            new_caption = format_caption(
                                template=caption_template,
                                filename=file_name,
                                original_caption=original_caption,
                                series_data=series_data
                            )
                        
                        # Copy message to Main DB with FloodWait handling
                        copied_msg = await msg.copy(
                            chat_id=MAIN_DB_CHANNEL,
                            caption=new_caption if new_caption else (msg.caption if hasattr(msg, 'caption') else None)
                        )
                        
                        main_db_message_ids.append(copied_msg.id)
                        copied_count += 1
                        
                        # Update progress every 10 messages
                        if copied_count % 10 == 0:
                            try:
                                await processing_msg.edit_text(
                                    f"<b>Copying to Main DB...⏳</b>\n"
                                    f"Progress: {copied_count}/{len(source_messages)}"
                                )
                            except:
                                pass
                        
                    except FloodWait as e:
                        logger.warning(f"FloodWait: Waiting {e.value} seconds while copying message {idx}...")
                        await processing_msg.edit_text(
                            f"<b>FloodWait: Waiting {e.value} seconds...⏳</b>\n"
                            f"Copied: {copied_count}/{len(source_messages)}"
                        )
                        await asyncio.sleep(e.value)
                        
                        # Retry copying this message after waiting
                        try:
                            copied_msg = await msg.copy(
                                chat_id=MAIN_DB_CHANNEL,
                                caption=new_caption if new_caption else (msg.caption if hasattr(msg, 'caption') else None)
                            )
                            main_db_message_ids.append(copied_msg.id)
                            copied_count += 1
                        except Exception as e:
                            logger.error(f"Error retrying copy of message {idx}: {e}")
                            
                    except Exception as e:
                        logger.error(f"Error copying message {idx}: {e}")
                
                if not main_db_message_ids:
                    await processing_msg.edit_text("❌ Error: Could not copy messages to Main DB!")
                    state_manager.clear_state(user_id)
                    return
                
                # Step 3: Create batch link using Main DB messages
                main_db_first_id = main_db_message_ids[0]
                main_db_last_id = main_db_message_ids[-1]
                
                # Generate batch link in plain format: get_{channel_id}_{first_msg}_{last_msg}
                channel_id_str = str(abs(MAIN_DB_CHANNEL))
                bot_username = (await client.get_me()).username
                batch_link = f"https://t.me/{bot_username}?start=get_{channel_id_str}_{main_db_first_id}_{main_db_last_id}"
                
                # Step 4: Save batch link and message IDs to database
                await db.update_quality_batch(
                    state.series_id,
                    state.lang_id,
                    state.season_id,
                    state.quality_id,
                    batch_link
                )
                
                # Also store the Main DB message range
                await db.set_batch_range(
                    state.series_id,
                    state.lang_id,
                    state.season_id,
                    state.quality_id,
                    main_db_first_id,
                    main_db_last_id,
                    MAIN_DB_CHANNEL
                )
                
                # Store batch mapping for reference
                quality_key = f"{state.series_id}:{state.lang_id}:{state.season_id}:{state.quality_id}"
                await batch_db.store_batch_mapping(
                    quality_key,
                    source_first_msg_id,
                    source_last_msg_id,
                    main_db_first_id,
                    main_db_last_id,
                    source_channel_id
                )
                
                # Update series message in update channel (if published)
                series = await db.get_series(state.series_id)
                if series and series.get('published', False):
                    await publish_update(client, state.series_id)
                
                # Update processing message with success
                await processing_msg.edit_text(
                    "<b>Successfully Added Batch ✅</b>\n"
                    f"• Total Messages: {len(main_db_message_ids)}"
                )
                
            except Exception as e:
                logger.error(f"Error in batch processing: {e}", exc_info=True)
                await processing_msg.edit_text(f"❌ Error: {str(e)}")
            
            finally:
                # Clean up temp data
                if hasattr(state_manager, 'temp_data') and user_id in state_manager.temp_data:
                    del state_manager.temp_data[user_id]
                
                state_manager.clear_state(user_id)
    
    except Exception as e:
        logger.error(f"Error handling batch: {e}", exc_info=True)
        await message.reply_text(f"❌ Error: {str(e)}")
        state_manager.clear_state(user_id)


# ============================================================================
# SEND BATCH FILES DIRECTLY
# ============================================================================

async def send_batch_files(client: Client, callback_query: CallbackQuery, series_id: str, lang_id: str, season_id: str, quality_id: str):
    """Send batch files directly when user clicks quality button in PM"""
    try:
        series = await db.get_series(series_id)
        if not series:
            await callback_query.answer("Series not found!", show_alert=True)
            return
        
        quality_data = series.get('languages', {}).get(lang_id, {}).get('seasons', {}).get(season_id, {}).get('qualities', {}).get(quality_id, {})
        
        # Get batch range
        first_msg_id = quality_data.get('first_msg_id')
        last_msg_id = quality_data.get('last_msg_id')
        db_channel_id = quality_data.get('db_channel_id')
        
        if not first_msg_id or not last_msg_id:
            await callback_query.answer("Batch not available!", show_alert=True)
            return
        
        # Answer callback first
        await callback_query.answer("📥 Sending files...")
        
        # Create list of message IDs
        if first_msg_id <= last_msg_id:
            ids = range(first_msg_id, last_msg_id + 1)
        else:
            ids = []
            i = first_msg_id
            while True:
                ids.append(i)
                i -= 1
                if i < last_msg_id:
                    break
        
        # Send in PM only
        chat_id = callback_query.from_user.id
        
        # Send a "Please wait" message
        temp_msg = await client.send_message(chat_id, "📥 Please wait, sending files...")
        
        try:
            # Determine which channel to get messages from
            # If db_channel_id matches MAIN_DB_CHANNEL, use Main DB
            # Otherwise, use the old DB channel
            if db_channel_id and MAIN_DB_CHANNEL and db_channel_id == MAIN_DB_CHANNEL:
                # Get messages from Main DB in batches of 200
                messages = []
                ids_list = list(ids)
                batch_size = 200
                
                for i in range(0, len(ids_list), batch_size):
                    batch_ids = ids_list[i:i + batch_size]
                    
                    try:
                        msgs = await client.get_messages(MAIN_DB_CHANNEL, batch_ids)
                        
                        # Filter out None messages
                        if isinstance(msgs, list):
                            messages.extend([msg for msg in msgs if msg is not None])
                        elif msgs is not None:
                            messages.append(msgs)
                            
                    except FloodWait as e:
                        logger.warning(f"FloodWait: Waiting {e.value} seconds...")
                        await asyncio.sleep(e.value)
                        
                        # Retry after waiting
                        try:
                            msgs = await client.get_messages(MAIN_DB_CHANNEL, batch_ids)
                            if isinstance(msgs, list):
                                messages.extend([msg for msg in msgs if msg is not None])
                            elif msgs is not None:
                                messages.append(msgs)
                        except Exception as e:
                            logger.error(f"Error retrying batch fetch: {e}")
                            
                    except Exception as e:
                        logger.error(f"Error fetching batch: {e}")
            else:
                # Get all messages from old DB channel in batch
                messages = await get_messages(client, list(ids))
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            await temp_msg.edit_text("❌ Error fetching files!")
            return
        
        await temp_msg.delete()
        
        # Send all messages - captions are already applied in Main DB
        for msg in messages:
            if msg:  # Skip if message is None (deleted)
                try:
                    # Messages from Main DB already have custom captions applied
                    # Just copy them as-is
                    from pyrogram import enums
                    await msg.copy(
                        chat_id=chat_id, 
                        caption=msg.caption.html if msg.caption else None,
                        parse_mode=enums.ParseMode.HTML
                    )
                    
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    # Retry
                    await msg.copy(
                        chat_id=chat_id, 
                        caption=msg.caption.html if msg.caption else None,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Error copying message: {e}")
                    continue
    
    except Exception as e:
        logger.error(f"Error sending batch: {e}", exc_info=True)
        await callback_query.answer("❌ Error sending files!", show_alert=True)


# ============================================================================
# SERIES SELECTION HANDLER
# ============================================================================

async def handle_series_selection(client: Client, callback_query: CallbackQuery, result_id: str):
    """Handle when user selects a series from search results"""
    try:
        metadata = await metadata_fetcher.fetch_metadata(result_id)
        
        if not metadata:
            await callback_query.answer("❌ Series data not found!", show_alert=True)
            return
        
        series_title = metadata.get('title', 'Unknown')
        imdb_id = metadata.get('id', '')
        
        # Check if series already exists
        existing = await db.series_exists(imdb_id=imdb_id, title=series_title)
        
        if existing:
            # Series already exists - show alert
            await callback_query.answer(
                f"{series_title} Already Added ✅",
                show_alert=True
            )
            return
        
        # Series doesn't exist - create new one
        series_id = str(uuid.uuid4())[:8]
        
        await db.add_series(
            series_id=series_id,
            title=series_title,
            year=metadata.get('year', ''),
            genre=metadata.get('genre', ''),
            rating=str(metadata.get('rating', '')),
            imdb_id=imdb_id,
            poster_url=metadata.get('poster', '')
        )
        
        await callback_query.message.delete()
        
        # Show popup alert instead of message
        await callback_query.answer(
            f"{series_title} added successfully ✅",
            show_alert=True
        )
        
        fake_msg = type('obj', (object,), {
            'chat': callback_query.message.chat,
            'reply_text': callback_query.message.reply_text,
            'reply_photo': callback_query.message.reply_photo
        })()
        await show_series_main_view(fake_msg, series_id)
        
    except Exception as e:
        logger.error(f"Error creating series: {e}", exc_info=True)
        await callback_query.answer(f"❌ Error: {str(e)}", show_alert=True)


# ============================================================================
# MAIN CALLBACK HANDLER
# ============================================================================

@Client.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    """Main callback query handler"""
    data = callback_query.data
    
    try:
        # ===== USER ACCESS CALLBACKS WITH BUTTON LOCK =====
        if data.startswith("userseries_"):
            parts = data.replace("userseries_", "").split("_")
            series_id = parts[0]
            
            # Check if this is from a group (has requester_id)
            if len(parts) > 1:
                requester_id = int(parts[1])
                # Validate requester in groups
                if callback_query.from_user.id != requester_id:
                    await callback_query.answer("Not your request!", show_alert=True)
                    return
            
            await show_user_series_view(callback_query, series_id, client=client)
            return
        
        elif data.startswith("userlang_"):
            parts = data.replace("userlang_", "").split("_")
            series_id = parts[0]
            lang_id = parts[1]
            
            # Check if this is from a group (has requester_id)
            if len(parts) > 2:
                requester_id = int(parts[2])
                # Validate requester in groups
                if callback_query.from_user.id != requester_id:
                    await callback_query.answer("Not your request!", show_alert=True)
                    return
            
            await show_user_series_view(callback_query, series_id, lang_id=lang_id, client=client)
            return
        
        elif data.startswith("userseason_"):
            parts = data.replace("userseason_", "").split("_")
            series_id = parts[0]
            lang_id = parts[1]
            season_id = parts[2]
            
            # Check if this is from a group (has requester_id)
            if len(parts) > 3:
                requester_id = int(parts[3])
                # Validate requester in groups
                if callback_query.from_user.id != requester_id:
                    await callback_query.answer("Not your request!", show_alert=True)
                    return
            
            await show_user_series_view(callback_query, series_id, lang_id=lang_id, season_id=season_id, client=client)
            return
        
        elif data.startswith("userquality_"):
            # User clicked quality - return URL with batch link in plain format
            parts = data.replace("userquality_", "").split("_", 3)
            series_id, lang_id, season_id, quality_id = parts
            
            # Get quality data
            series = await db.get_series(series_id)
            if not series:
                await callback_query.answer("Series not found!", show_alert=True)
                return
            
            quality_data = series.get('languages', {}).get(lang_id, {}).get('seasons', {}).get(season_id, {}).get('qualities', {}).get(quality_id, {})
            
            # Get batch range
            first_msg_id = quality_data.get('first_msg_id')
            last_msg_id = quality_data.get('last_msg_id')
            db_channel_id = quality_data.get('db_channel_id', client.main_db_channel.id)
            
            if not first_msg_id or not last_msg_id:
                await callback_query.answer("Batch not available!", show_alert=True)
                return
            
            # Generate plain format batch link: get_{channel_id}_{first_msg}_{last_msg}
            # Remove the -100 prefix from channel_id for the link
            channel_id_str = str(abs(db_channel_id))
            batch_parameter = f"get_{channel_id_str}_{first_msg_id}_{last_msg_id}"
            
            # Get bot username
            bot_username = (await client.get_me()).username
            batch_url = f"https://t.me/{bot_username}?start={batch_parameter}"
            
            # Return URL via callback answer
            await callback_query.answer(url=batch_url)
            return
        
        # ===== ADMIN CALLBACKS =====
        
        # Handle series selection from search
        if data.startswith("selectseries_"):
            result_id = data.replace("selectseries_", "")
            await handle_series_selection(client, callback_query, result_id)
            return
        
        elif data == "cancel_search":
            await callback_query.message.edit_text("❌ Search cancelled.")
            return
        
        # Publish/Unpublish series
        elif data.startswith("publish_series_"):
            series_id = data.replace("publish_series_", "")
            series = await db.get_series(series_id)
            
            if not series:
                await callback_query.answer("Series not found!", show_alert=True)
                return
            
            # Toggle publish status
            is_published = series.get('published', False)
            new_status = not is_published
            
            await db.publish_series(series_id, new_status)
            
            # Send or update message in update channel
            if new_status:
                # Send/update message when publishing
                await publish_update(client, series_id)
            # Note: We don't delete the message when unpublishing, as per requirements
            
            # Delete the management message
            try:
                await callback_query.message.delete()
            except:
                pass
            
            # Send confirmation message
            series_title = series.get('title', 'Unknown')
            if new_status:
                await callback_query.message.reply_text(
                    f"Series <b>{series_title}</b> Published! ✅"
                )
            else:
                await callback_query.message.reply_text(
                    f"🔴 Series <b>{series_title}</b> Unpublished!"
                )
            
            await callback_query.answer()
            return
        
        # Update poster
        elif data.startswith("update_poster_"):
            series_id = data.replace("update_poster_", "")
            await handle_update_poster(client, callback_query, series_id)
            return
        
        # Edit details
        elif data.startswith("edit_details_"):
            series_id = data.replace("edit_details_", "")
            await handle_edit_details(client, callback_query, series_id)
            return
        
        # Series view
        elif data.startswith("series_"):
            series_id = data.split("_", 1)[1]
            await show_series_main_view(callback_query, series_id)
        
        # Add language
        elif data.startswith("addlang_"):
            series_id = data.split("_", 1)[1]
            await handle_add_language(client, callback_query, series_id)
        
        # Language view
        elif data.startswith("lang_"):
            parts = data.split("_")
            series_id = parts[1]
            lang_id = "_".join(parts[2:])
            await show_series_main_view(callback_query, series_id, lang_id=lang_id)
        
        # Add season
        elif data.startswith("addseason_"):
            parts = data.replace("addseason_", "").split("_", 1)
            series_id, lang_id = parts
            await handle_add_season(client, callback_query, series_id, lang_id)
        
        # Season view
        elif data.startswith("season_"):
            parts = data.split("_", 3)
            series_id = parts[1]
            lang_id = parts[2]
            season_id = parts[3]
            await show_series_main_view(callback_query, series_id, lang_id=lang_id, season_id=season_id)
        
        # Add quality
        elif data.startswith("addquality_"):
            parts = data.replace("addquality_", "").split("_", 2)
            series_id, lang_id, season_id = parts
            await handle_add_quality(client, callback_query, series_id, lang_id, season_id)
        
        # Quality selection - Start batch process
        elif data.startswith("quality_"):
            parts = data.replace("quality_", "").split("_", 3)
            series_id, lang_id, season_id, quality_id = parts
            await handle_quality_click(client, callback_query, series_id, lang_id, season_id, quality_id)
        
        # Delete series - show confirmation
        elif data.startswith("delete_series_"):
            series_id = data.replace("delete_series_", "")
            series = await db.get_series(series_id)
            
            if not series:
                await callback_query.answer("Series not found!", show_alert=True)
                return
            
            buttons = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_delete_series_{series_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"series_{series_id}")
                ]
            ]
            await callback_query.answer()
            msg = callback_query.message
            try:
                if msg.photo:
                    await msg.edit_caption(
                        caption=f"⚠️ Are you sure you want to delete series <b>'{series.get('title', 'Unknown')}'</b>?\n\nThis will delete all languages, seasons, and episodes.",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                else:
                    await msg.edit_text(
                        f"⚠️ Are you sure you want to delete series <b>'{series.get('title', 'Unknown')}'</b>?\n\nThis will delete all languages, seasons, and episodes.",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
            except Exception as e:
                logger.error(f"Error editing message for delete series confirmation: {e}")
        
        # Confirm delete series
        elif data.startswith("confirm_delete_series_"):
            series_id = data.replace("confirm_delete_series_", "")
            series = await db.get_series(series_id)
            
            if not series:
                await callback_query.answer("Series not found!", show_alert=True)
                return
            
            series_title = series.get('title', 'Unknown')
            
            # Delete the update message from update channel
            await delete_series_update_message(client, series_id)
            
            # Delete the series
            await db.delete_series(series_id)
            
            await callback_query.answer("Series deleted! ✅", show_alert=True)
            
            # Edit the message in place to show success
            msg = callback_query.message
            try:
                if msg.photo:
                    await msg.edit_caption(caption=f"Series <b>'{series_title}'</b> deleted successfully! ✅")
                else:
                    await msg.edit_text(f"Series <b>'{series_title}'</b> deleted successfully! ✅")
            except Exception as e:
                logger.error(f"Error editing message after delete series: {e}")
        
        # Delete language - show confirmation
        elif data.startswith("deletelang_"):
            parts = data.replace("deletelang_", "").split("_", 1)
            series_id, lang_id = parts
            
            series = await db.get_series(series_id)
            lang_name = series.get('languages', {}).get(lang_id, {}).get('name', 'Unknown') if series else 'Unknown'
            
            buttons = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_deletelang_{series_id}_{lang_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"lang_{series_id}_{lang_id}")
                ]
            ]
            await callback_query.answer()
            msg = callback_query.message
            try:
                if msg.photo:
                    await msg.edit_caption(
                        caption=f"⚠️ Are you sure you want to delete language <b>'{lang_name}'</b>?\n\nThis will delete all seasons and episodes in this language.",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                else:
                    await msg.edit_text(
                        f"⚠️ Are you sure you want to delete language <b>'{lang_name}'</b>?\n\nThis will delete all seasons and episodes in this language.",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
            except Exception as e:
                logger.error(f"Error editing message for delete language confirmation: {e}")
        
        # Confirm delete language
        elif data.startswith("confirm_deletelang_"):
            parts = data.replace("confirm_deletelang_", "").split("_", 1)
            series_id, lang_id = parts
            
            await db.delete_language(series_id, lang_id)
            
            # Update series message in update channel (if published)
            series = await db.get_series(series_id)
            if series and series.get('published', False):
                await publish_update(client, series_id)
            
            await callback_query.answer("Language deleted! ✅", show_alert=True)
            await show_series_main_view(callback_query, series_id)
        
        # Delete season - show confirmation
        elif data.startswith("deleteseason_"):
            parts = data.replace("deleteseason_", "").split("_", 2)
            series_id, lang_id, season_id = parts
            
            series = await db.get_series(series_id)
            season_name = series.get('languages', {}).get(lang_id, {}).get('seasons', {}).get(season_id, {}).get('name', 'Unknown') if series else 'Unknown'
            
            buttons = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_deleteseason_{series_id}_{lang_id}_{season_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"season_{series_id}_{lang_id}_{season_id}")
                ]
            ]
            await callback_query.answer()
            msg = callback_query.message
            try:
                if msg.photo:
                    await msg.edit_caption(
                        caption=f"⚠️ Are you sure you want to delete season <b>'{season_name}'</b>?\n\nThis will delete all episodes and qualities in this season.",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                else:
                    await msg.edit_text(
                        f"⚠️ Are you sure you want to delete season <b>'{season_name}'</b>?\n\nThis will delete all episodes and qualities in this season.",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
            except Exception as e:
                logger.error(f"Error editing message for delete season confirmation: {e}")
        
        # Confirm delete season
        elif data.startswith("confirm_deleteseason_"):
            parts = data.replace("confirm_deleteseason_", "").split("_", 2)
            series_id, lang_id, season_id = parts
            
            await db.delete_season(series_id, lang_id, season_id)
            
            # Update series message in update channel (if published)
            series = await db.get_series(series_id)
            if series and series.get('published', False):
                await publish_update(client, series_id)
            
            await callback_query.answer("Season deleted! ✅", show_alert=True)
            await show_series_main_view(callback_query, series_id, lang_id=lang_id)
        
        # Delete quality
        elif data.startswith("deletequality_"):
            parts = data.replace("deletequality_", "").split("_", 3)
            series_id, lang_id, season_id, quality_id = parts
            
            await db.delete_quality(series_id, lang_id, season_id, quality_id)
            
            # Update series message in update channel (if published)
            series = await db.get_series(series_id)
            if series and series.get('published', False):
                await publish_update(client, series_id)
            
            await callback_query.answer("Quality deleted! ✅", show_alert=True)
            await show_series_main_view(callback_query, series_id, lang_id=lang_id, season_id=season_id)
        
        # Confirm delete all series
        elif data == "confirmdelall":
            count = await db.delete_all_series()
            await callback_query.message.edit_text(
                f"Successfully deleted <b>{count} series</b> and all related data! ✅"
            )
        
        # Cancel delete
        elif data == "cancel_delete":
            await callback_query.message.edit_text("❌ Delete operation cancelled.")
        
        # ===== EPISODE CALLBACKS =====
        
        # Add episode
        elif data.startswith("addepisode_"):
            parts = data.replace("addepisode_", "").split("_", 2)
            series_id, lang_id, season_id = parts
            await handle_add_episode(client, callback_query, series_id, lang_id, season_id)
        
        # Clear episodes - show confirmation
        elif data.startswith("clearepisodes_"):
            parts = data.replace("clearepisodes_", "").split("_", 2)
            series_id, lang_id, season_id = parts
            
            series = await db.get_series(series_id)
            season_name = series.get('languages', {}).get(lang_id, {}).get('seasons', {}).get(season_id, {}).get('name', 'Unknown') if series else 'Unknown'
            
            buttons = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_clearepisodes_{series_id}_{lang_id}_{season_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"season_{series_id}_{lang_id}_{season_id}")
                ]
            ]
            await callback_query.answer()
            msg = callback_query.message
            try:
                if msg.photo:
                    await msg.edit_caption(
                        caption=f"⚠️ Are you sure you want to clear all episodes from <b>'{season_name}'</b>?\n\nAll episode buttons and files will be removed.",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                else:
                    await msg.edit_text(
                        f"⚠️ Are you sure you want to clear all episodes from <b>'{season_name}'</b>?\n\nAll episode buttons and files will be removed.",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
            except Exception as e:
                logger.error(f"Error editing message for clear episodes confirmation: {e}")
        
        # Confirm clear episodes
        elif data.startswith("confirm_clearepisodes_"):
            parts = data.replace("confirm_clearepisodes_", "").split("_", 2)
            series_id, lang_id, season_id = parts
            
            await db.clear_episodes(series_id, lang_id, season_id)
            
            # Update series message in update channel (if published)
            series = await db.get_series(series_id)
            if series and series.get('published', False):
                await publish_update(client, series_id)
            
            await callback_query.answer("All episodes cleared! ✅", show_alert=True)
            await show_series_main_view(callback_query, series_id, lang_id=lang_id, season_id=season_id)
        
        # Episode view (admin)
        elif data.startswith("episode_"):
            parts = data.replace("episode_", "").split("_", 3)
            series_id, lang_id, season_id, episode_id = parts
            await show_episode_admin_view(callback_query, series_id, lang_id, season_id, episode_id)
        
        # Add quality to episode
        elif data.startswith("addepquality_"):
            parts = data.replace("addepquality_", "").split("_", 3)
            series_id, lang_id, season_id, episode_id = parts
            await handle_add_episode_quality(client, callback_query, series_id, lang_id, season_id, episode_id)
        
        # Episode quality click (admin - to add file)
        elif data.startswith("epquality_"):
            parts = data.replace("epquality_", "").split("_", 4)
            series_id, lang_id, season_id, episode_id, quality_id = parts
            await handle_episode_quality_click(client, callback_query, series_id, lang_id, season_id, episode_id, quality_id)
        
        # Delete episode - show confirmation
        elif data.startswith("deleteepisode_"):
            parts = data.replace("deleteepisode_", "").split("_", 3)
            series_id, lang_id, season_id, episode_id = parts
            
            series = await db.get_series(series_id)
            ep_name = series.get('languages', {}).get(lang_id, {}).get('seasons', {}).get(season_id, {}).get('episodes', {}).get(episode_id, {}).get('name', 'Unknown') if series else 'Unknown'
            
            buttons = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_deleteepisode_{series_id}_{lang_id}_{season_id}_{episode_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"episode_{series_id}_{lang_id}_{season_id}_{episode_id}")
                ]
            ]
            await callback_query.answer()
            msg = callback_query.message
            try:
                if msg.photo:
                    await msg.edit_caption(
                        caption=f"⚠️ Are you sure you want to delete episode <b>'{ep_name}'</b>?",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                else:
                    await msg.edit_text(
                        f"⚠️ Are you sure you want to delete episode <b>'{ep_name}'</b>?",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
            except Exception as e:
                logger.error(f"Error editing message for delete episode confirmation: {e}")
        
        # Confirm delete episode
        elif data.startswith("confirm_deleteepisode_"):
            parts = data.replace("confirm_deleteepisode_", "").split("_", 3)
            series_id, lang_id, season_id, episode_id = parts
            await db.delete_episode(series_id, lang_id, season_id, episode_id)
            await callback_query.answer("Episode deleted! ✅", show_alert=True)
            await show_series_main_view(callback_query, series_id, lang_id=lang_id, season_id=season_id)
        
        # Delete episode quality
        elif data.startswith("delepquality_"):
            parts = data.replace("delepquality_", "").split("_", 4)
            series_id, lang_id, season_id, episode_id, quality_id = parts
            await db.delete_episode_quality(series_id, lang_id, season_id, episode_id, quality_id)
            await callback_query.answer("Episode quality deleted! ✅", show_alert=True)
            await show_episode_admin_view(callback_query, series_id, lang_id, season_id, episode_id)
        
        # User episode quality - send file link
        elif data.startswith("userepquality_"):
            parts = data.replace("userepquality_", "").split("_", 4)
            series_id, lang_id, season_id, episode_id, quality_id = parts
            series = await db.get_series(series_id)
            if not series:
                await callback_query.answer("Series not found!", show_alert=True)
                return
            ep_data = series.get('languages', {}).get(lang_id, {}).get('seasons', {}).get(season_id, {}).get('episodes', {}).get(episode_id, {})
            quality_data = ep_data.get('qualities', {}).get(quality_id, {})
            file_link = quality_data.get('file_link')
            if not file_link:
                await callback_query.answer("File not available!", show_alert=True)
                return
            await callback_query.answer(url=file_link)
        
        # User episode view - show qualities for that episode
        elif data.startswith("userepisode_"):
            parts = data.replace("userepisode_", "").split("_", 3)
            series_id, lang_id, season_id, episode_id = parts
            series = await db.get_series(series_id)
            if not series:
                await callback_query.answer("Series not found!", show_alert=True)
                return
            lang_data = series.get('languages', {}).get(lang_id, {})
            season_data = lang_data.get('seasons', {}).get(season_id, {})
            episode_data = season_data.get('episodes', {}).get(episode_id, {})
            
            text = build_series_info_text(series)
            text += f"<pre><b>▪️Language:</b> <code>{lang_data.get('name', 'Unknown')}</code></pre>\n"
            text += f"<pre><b>▪️Season:</b> <code>{season_data.get('name', 'Unknown')}</code></pre>\n"
            text += f"<pre><b>▪️Episode:</b> <code>{episode_data.get('name', 'Unknown')}</code></pre>\n"
            text += "<i>Select the quality you need...!</i>"
            
            buttons = []
            quality_buttons = []
            for q_id_key, q_data in episode_data.get('qualities', {}).items():
                if q_data.get('published') and q_data.get('file_link'):
                    quality_buttons.append(
                        InlineKeyboardButton(
                            q_data.get('name', 'Unknown'),
                            callback_data=f"userepquality_{series_id}_{lang_id}_{season_id}_{episode_id}_{q_id_key}"
                        )
                    )
            if quality_buttons:
                buttons.extend(group_buttons_in_rows(quality_buttons, 2))
            else:
                text += "\n\n❌ No qualities available yet."
            
            buttons.append([InlineKeyboardButton("⪻ Back", callback_data=f"userseason_{series_id}_{lang_id}_{season_id}")])
            markup = InlineKeyboardMarkup(buttons)
            
            msg = callback_query.message
            try:
                if msg.photo:
                    await msg.edit_caption(caption=text, reply_markup=markup)
                else:
                    await msg.edit_text(text, reply_markup=markup)
            except Exception as e:
                logger.error(f"Error showing user episode view: {e}")
                await msg.reply_text(text, reply_markup=markup)
        
        else:
            await callback_query.answer("Unknown action!")
    
    except Exception as e:
        logger.error(f"Error in callback handler: {e}", exc_info=True)
        await callback_query.answer("An error occurred. Please try again.", show_alert=True)


# ============================================================================
# FORWARDED MESSAGE HANDLER
# ============================================================================

@Client.on_message(filters.private & (filters.forwarded | (filters.text & filters.regex(r't\.me/'))))
async def forwarded_handler(client: Client, message: Message):
    """
    Handle forwarded messages or DB channel post links for batch system
    Accepts: forwarded messages (any type: text, photo, video, etc.) or t.me/ links
    """
    await handle_forwarded_or_link(client, message)


# ============================================================================
# PHOTO MESSAGE HANDLER
# ============================================================================

@Client.on_message(filters.private & filters.photo & filters.user(ADMINS))
async def photo_handler(client: Client, message: Message):
    """Handle photo messages for poster updates"""
    await handle_photo_input(client, message)


# ============================================================================
# EPISODE SINGLE FILE HANDLER
# ============================================================================

@Client.on_message(filters.private & auth_filter & (filters.document | filters.video | filters.audio))
async def episode_file_handler(client: Client, message: Message):
    """Handle single file uploads for episode qualities"""
    user_id = message.from_user.id
    state = state_manager.get_state(user_id)
    
    if not state or state.action != 'adding_episode_file':
        return
    
    if not MAIN_DB_CHANNEL:
        await message.reply_text("⚠️ Main DB Channel is not configured!")
        state_manager.clear_state(user_id)
        return
    
    processing_msg = await message.reply_text("⏳ Processing...")
    
    try:
        # Get series data for caption
        series_doc = await db.get_series(state.series_id)
        
        # Build caption
        file_name = "Unknown"
        if message.document:
            file_name = message.document.file_name or "Unknown"
        elif message.video:
            file_name = message.video.file_name or "video.mp4"
        elif message.audio:
            file_name = message.audio.file_name or "audio.mp3"
        
        original_caption = message.caption or ""
        caption_template = await get_caption_template(user_id)
        if caption_template == "{filename}":
            caption_template = CUSTOM_FILE_CAPTION
        
        series_name = series_doc.get('title', '') if series_doc else ''
        language = ''
        quality = ''
        episode_name = ''
        
        if series_doc:
            lang_data = series_doc.get('languages', {}).get(state.lang_id, {})
            language = lang_data.get('name', '')
            season_data = lang_data.get('seasons', {}).get(state.season_id, {})
            episode_data = season_data.get('episodes', {}).get(state.episode_id, {})
            episode_name = episode_data.get('name', '')
            quality_data = episode_data.get('qualities', {}).get(state.quality_id, {})
            quality = quality_data.get('name', '')
        
        series_data = {
            'series_name': series_name,
            'language': language,
            'quality': quality,
            'episode': episode_name
        }
        
        new_caption = format_caption(
            template=caption_template,
            filename=file_name,
            original_caption=original_caption,
            series_data=series_data
        )
        
        # Copy file to Main DB channel
        copied_msg = await message.copy(
            chat_id=MAIN_DB_CHANNEL,
            caption=new_caption if new_caption else original_caption
        )
        
        # Get bot username for link
        bot_me = await client.get_me()
        bot_username = bot_me.username
        file_link = f"https://t.me/{bot_username}?start=get_{str(abs(MAIN_DB_CHANNEL))}_{copied_msg.id}_{copied_msg.id}"
        
        # Save to DB
        await db.set_episode_quality_file(
            state.series_id,
            state.lang_id,
            state.season_id,
            state.episode_id,
            state.quality_id,
            copied_msg.id,
            file_link
        )
        
        # Update series in update channel if published
        if series_doc and series_doc.get('published', False):
            try:
                await publish_update(client, state.series_id)
            except Exception as e:
                logger.error(f"Error updating update channel: {e}")
        
        await processing_msg.edit_text("File added successfully ✅")
        
        # Delete the bot's prompt message and user's file message
        try:
            # Delete user's file message
            await message.delete()
        except:
            pass
        try:
            # Delete bot's prompt message (the one before user's message)
            await client.delete_messages(message.chat.id, message.id - 1)
        except:
            pass
        try:
            # Delete processing message
            await processing_msg.delete()
        except:
            pass
        
        # Edit the original episode admin view message in place - never send a new one
        try:
            main_msg = await client.get_messages(message.chat.id, state.message_id)
            # Re-fetch updated series data
            updated_series = await db.get_series(state.series_id)
            lang_data = updated_series.get('languages', {}).get(state.lang_id, {})
            season_data = lang_data.get('seasons', {}).get(state.season_id, {})
            episode_data = season_data.get('episodes', {}).get(state.episode_id, {})
            
            text = build_series_info_text(updated_series)
            text += f"<pre><b>\u25aa\ufe0fLanguage:</b> <code>{lang_data.get('name', 'Unknown')}</code></pre>\n"
            text += f"<pre><b>\u25aa\ufe0fSeason:</b> <code>{season_data.get('name', 'Unknown')}</code></pre>\n"
            text += f"<pre><b>\u25aa\ufe0fEpisode:</b> <code>{episode_data.get('name', 'Unknown')}</code></pre>\n"
            text += "<b>Select a quality or add new:</b>"
            
            buttons = []
            if episode_data.get('qualities'):
                quality_buttons = []
                for quality_id_key, quality_data in episode_data['qualities'].items():
                    quality_buttons.append(
                        InlineKeyboardButton(
                            quality_data.get('name', 'Unknown'),
                            callback_data=f"epquality_{state.series_id}_{state.lang_id}_{state.season_id}_{state.episode_id}_{quality_id_key}"
                        )
                    )
                buttons.extend(group_buttons_in_rows(quality_buttons, 2))
            buttons.extend([
                [InlineKeyboardButton("\u2795 Add Quality", callback_data=f"addepquality_{state.series_id}_{state.lang_id}_{state.season_id}_{state.episode_id}")],
                [InlineKeyboardButton("\U0001f5d1\ufe0f Delete Episode", callback_data=f"deleteepisode_{state.series_id}_{state.lang_id}_{state.season_id}_{state.episode_id}")],
                [InlineKeyboardButton("\u2aab Back", callback_data=f"season_{state.series_id}_{state.lang_id}_{state.season_id}")]
            ])
            markup = InlineKeyboardMarkup(buttons)
            
            # Edit in place only - never reply/send new message
            try:
                if main_msg.photo:
                    poster_url = updated_series.get('poster_url', '')
                    if poster_url:
                        from pyrogram.types import InputMediaPhoto
                        await main_msg.edit_media(
                            media=InputMediaPhoto(media=poster_url, caption=text),
                            reply_markup=markup
                        )
                    else:
                        await main_msg.edit_caption(caption=text, reply_markup=markup)
                else:
                    await main_msg.edit_text(text, reply_markup=markup)
            except Exception as edit_err:
                logger.error(f"Error editing episode admin view in place: {edit_err}")
        except Exception as e:
            logger.error(f"Error updating episode admin view: {e}")
    
    except Exception as e:
        logger.error(f"Error handling episode file: {e}", exc_info=True)
        await processing_msg.edit_text(f"❌ Error: {str(e)}")
    
    finally:
        state_manager.clear_state(user_id)
