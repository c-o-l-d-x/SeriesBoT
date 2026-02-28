import os
import sys
import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message
from auth_manager import auth_manager
from info import ADMINS, DATABASE_URI, DATABASE_NAME

# Bot start time for uptime calculation
BOT_START_TIME = datetime.now()


def get_uptime():
    """Calculate bot uptime in readable format"""
    uptime = datetime.now() - BOT_START_TIME
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    return ", ".join(parts)


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMINS


def is_auth_user_or_admin(user_id: int) -> bool:
    """Check if user is auth user or admin"""
    return is_admin(user_id) or auth_manager.is_auth_user(user_id)


def auth_filter():
    """Custom filter that allows both admins and auth users"""
    allowed_users = list(set(ADMINS + auth_manager.get_all_auth_users()))
    return filters.user(allowed_users)


# ==================== RESTART COMMAND ====================
@Client.on_message(filters.command("restart") & filters.private & filters.user(ADMINS))
async def restart_bot(client: Client, message: Message):
    """Restart the bot - Admins only"""
    restart_msg = await message.reply_text("🔄 <b>Restarting Bot...</b>\n\nPlease wait a moment.", parse_mode=ParseMode.HTML)
    
    # Save restart info for post-restart notification (optional)
    try:
        with open('.restart_info', 'w') as f:
            f.write(f"{message.chat.id}\n{restart_msg.id}")
    except:
        pass
    
    # Restart the bot
    os.execl(sys.executable, sys.executable, *sys.argv)


# ==================== ADD AUTH USER ====================
@Client.on_message(filters.command("add_auth") & filters.private & filters.user(ADMINS))
async def add_auth_user(client: Client, message: Message):
    """Add auth user - Admins only"""
    
    # Parse user ID from command
    try:
        if len(message.command) < 2:
            await message.reply_text(
                "❌ <b>Incorrect Usage!</b>\n\n"
                "<b>Usage:</b> <code>/add_auth <user_id></code>\n\n"
                "<b>Example:</b> <code>/add_auth 123456789</code>"
            )
            return
        
        target_user_id = int(message.command[1])
        
        # Check if user is already admin
        if is_admin(target_user_id):
            await message.reply_text("ℹ️ <b>Already Admin!</b>\n\nThis user is already an admin and has all permissions.", parse_mode=ParseMode.HTML)
            return
        
        # Add auth user
        if await auth_manager.add_auth_user(target_user_id):
            # Try to get user info
            try:
                user = await client.get_users(target_user_id)
                user_mention = user.mention
                user_name = user.first_name
            except:
                user_mention = f"<code>{target_user_id}</code>"
                user_name = "User"
            
            await message.reply_text(
                f"✅ <b>Auth User Added!</b>\n\n"
                f"<b>User:</b> {user_mention}\n"
                f"<b>ID:</b> <code>{target_user_id}</code>\n\n"
                f"This user can now use auth-level commands."
            )
        else:
            await message.reply_text(
                f"ℹ️ <b>Already Auth User!</b>\n\n"
                f"User <code>{target_user_id}</code> is already in the auth users list."
            )
    
    except ValueError:
        await message.reply_text("❌ <b>Invalid User ID!</b>\n\nPlease provide a valid numeric user ID.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply_text(f"❌ <b>Error:</b> {str(e)}", parse_mode=ParseMode.HTML)


# ==================== DELETE AUTH USER ====================
@Client.on_message(filters.command("del_auth") & filters.private & filters.user(ADMINS))
async def delete_auth_user(client: Client, message: Message):
    """Delete auth user - Admins only"""
    
    # Parse user ID from command
    try:
        if len(message.command) < 2:
            await message.reply_text(
                "❌ <b>Incorrect Usage!</b>\n\n"
                "<b>Usage:</b> <code>/del_auth <user_id></code>\n\n"
                "<b>Example:</b> <code>/del_auth 123456789</code>"
            )
            return
        
        target_user_id = int(message.command[1])
        
        # Remove auth user
        if await auth_manager.remove_auth_user(target_user_id):
            # Try to get user info
            try:
                user = await client.get_users(target_user_id)
                user_mention = user.mention
            except:
                user_mention = f"<code>{target_user_id}</code>"
            
            await message.reply_text(
                f"✅ <b>Auth User Removed!</b>\n\n"
                f"<b>User:</b> {user_mention}\n"
                f"<b>ID:</b> <code>{target_user_id}</code>\n\n"
                f"This user no longer has auth-level permissions."
            )
        else:
            await message.reply_text(
                f"ℹ️ <b>Not Found!</b>\n\n"
                f"User <code>{target_user_id}</code> is not in the auth users list."
            )
    
    except ValueError:
        await message.reply_text("❌ <b>Invalid User ID!</b>\n\nPlease provide a valid numeric user ID.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply_text(f"❌ <b>Error:</b> {str(e)}", parse_mode=ParseMode.HTML)


# ==================== VIEW AUTH USERS ====================
@Client.on_message(filters.command("authusers") & filters.private & filters.user(ADMINS))
async def view_auth_users(client: Client, message: Message):
    """View all auth users - Admins only"""
    
    auth_users = auth_manager.get_all_auth_users()
    
    if not auth_users:
        await message.reply_text(
            "📋 <b>AUTH USERS LIST</b>\n\n"
            "No auth users found.\n\n"
            "Use <code>/add_auth <user_id></code> to add auth users."
        )
        return
    
    # Build the auth users list
    text = "📋 <b>AUTH USERS LIST</b>\n\n"
    
    for idx, auth_user_id in enumerate(auth_users, 1):
        try:
            user = await client.get_users(auth_user_id)
            name = user.first_name
            if user.last_name:
                name += f" {user.last_name}"
            text += f"{idx}. {name} - <code>{auth_user_id}</code>\n"
        except:
            text += f"{idx}. User - <code>{auth_user_id}</code>\n"
    
    text += f"\n<b>Total Auth Users:</b> {len(auth_users)}"
    
    await message.reply_text(text)


# ==================== ENHANCED PING COMMAND ====================
# This replaces the existing ping command in broadcast_fixed.py
@Client.on_message(filters.command("ping") & auth_filter())
async def ping_with_uptime(client: Client, message: Message):
    """Enhanced ping with uptime - Auth users and Admins"""
    start_time = time.time()
    reply = await message.reply_text("🏓 Pinging...")
    end_time = time.time()
    
    response_time = (end_time - start_time) * 1000  # Convert to milliseconds
    uptime = get_uptime()
    
    await reply.edit_text(
        f"🏓 <b>Pong!</b>\n"
        f"⏱️ <b>Response Time:</b> <code>{response_time:.2f}ms</code>\n"
        f"🏃🏻‍♂️ <b>Bot Uptime:</b> <code>{uptime}</code>"
    )


# ==================== STATUS COMMAND ====================
@Client.on_message(filters.command("status") & filters.private & auth_filter())
async def status_command(client: Client, message: Message):
    """Show bot statistics - Admins and Auth Users"""
    try:
        from database.series_db import db as series_db
        from database.database import db as users_db
        from database.chat_db import chat_db
        import motor.motor_asyncio

        loading_msg = await message.reply_text("⏳ Fetching stats...")

        # Series count
        try:
            series_count = await series_db.get_series_count()
        except Exception:
            series_count = "N/A"

        # Active users (excluding blocked/deactivated)
        try:
            users_count = await users_db.total_users_count()
        except Exception:
            users_count = "N/A"

        # Chats count
        try:
            chats_count = await chat_db.chats.count_documents({})
        except Exception:
            chats_count = "N/A"

        # MongoDB storage via dbStats command
        storage_str = "N/A"
        try:
            mongo_client = motor.motor_asyncio.AsyncIOMotorClient(DATABASE_URI)
            stats = await mongo_client[DATABASE_NAME].command("dbStats", scale=1024 * 1024)
            used_mb = round(stats.get("dataSize", 0) / 1, 2)   # already in MB (scale=1MB)
            storage_size_mb = round(stats.get("storageSize", 0) / 1, 2)
            # MongoDB Atlas free tier is 512 MB
            total_mb = 512
            storage_str = f"{used_mb}mb/{total_mb}mb"
            mongo_client.close()
        except Exception as e:
            storage_str = "N/A"

        text = (
            "<b>📊 Bot Status</b>\n\n"
            f"<b>• Total Series :</b> <code>{series_count}</code>\n"
            f"<b>• Total Users :</b> <code>{users_count}</code>\n"
            f"<b>• Total Chats :</b> <code>{chats_count}</code>\n"
            f"<b>• Storage :</b> <code>{storage_str}</code>"
        )

        await loading_msg.edit_text(text)

    except Exception as e:
        await message.reply_text(f"❌ <b>Error fetching status:</b> <code>{e}</code>")
