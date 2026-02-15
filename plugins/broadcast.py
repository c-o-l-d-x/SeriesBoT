# -*- coding: utf-8 -*-
import os
import time
import asyncio
import logging
import datetime
from info import ADMINS
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import (
    FloodWait, 
    InputUserDeactivated, 
    UserIsBlocked, 
    PeerIdInvalid,
    ChatWriteForbidden,
    UserNotParticipant
)
from database.database import db
from database.chat_db import chat_db

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# =================== USER STATISTICS ===================

@Client.on_message(filters.command("users") & filters.user(ADMINS))
async def get_stats(bot: Client, message: Message):
    """Get detailed user statistics"""
    mr = await message.reply('<b>📊 ACCESSING DETAILS...</b>')
    
    try:
        stats = await db.get_user_stats()
        
        stats_text = f"""
<b>📊 USER STATISTICS</b>

👥 <b>Total Users:</b> <code>{stats['total']}</code>
✅ <b>Active Users:</b> <code>{stats['active']}</code>
🚫 <b>Blocked Bot:</b> <code>{stats['blocked']}</code>
❌ <b>Deactivated:</b> <code>{stats['deactivated']}</code>

📅 <b>Last Updated:</b> <code>{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>
"""
        await mr.edit(text=stats_text)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await mr.edit("❌ Error fetching statistics!")


# =================== BROADCAST SYSTEM ===================

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_handler(bot: Client, m: Message):
    """
    Enhanced broadcast system with:
    - FloodWait handling
    - Automatic cleanup of inactive users
    - Detailed progress tracking
    - Better error handling
    """
    
    all_users = await db.get_all_active_users()
    broadcast_msg = m.reply_to_message
    
    # Initial status message
    sts_msg = await m.reply_text("🚀 <b>Broadcast Started!</b>\n\n⏳ Preparing...", parse_mode=ParseMode.HTML)
    
    # Counters
    done = 0
    failed = 0
    success = 0
    blocked = 0
    deactivated = 0
    flood_errors = 0
    
    start_time = time.time()
    total_users = await db.total_users_count()
    
    async for user in all_users:
        user_id = user['_id']
        
        # Send message and get status
        sts, error_type = await send_msg(user_id, broadcast_msg)
        
        if sts == 200:
            success += 1
        elif sts == 400:
            failed += 1
            # Mark user based on error type
            if error_type == 'blocked':
                blocked += 1
                await db.mark_user_blocked(user_id)
            elif error_type == 'deactivated':
                deactivated += 1
                await db.mark_user_deactivated(user_id)
        elif sts == 429:
            flood_errors += 1
        else:
            failed += 1
        
        done += 1
        
        # Update progress every 100 users AND with a minimum time gap to avoid FloodWait
        if done % 100 == 0:
            # Only update if at least 3 seconds have passed since last update
            current_time = time.time()
            if not hasattr(broadcast_handler, 'last_update_time'):
                broadcast_handler.last_update_time = 0
            
            if current_time - broadcast_handler.last_update_time >= 3:
                elapsed_time = datetime.timedelta(seconds=int(time.time() - start_time))
                progress_text = f"""
🚀 <b>Broadcast in Progress</b>

📊 <b>Progress:</b> {done} / {total_users}
✅ <b>Successful:</b> {success}
❌ <b>Failed:</b> {failed}
🚫 <b>Blocked:</b> {blocked}
💤 <b>Deactivated:</b> {deactivated}
⏰ <b>FloodWait:</b> {flood_errors}

⏱️ <b>Elapsed Time:</b> <code>{elapsed_time}</code>
"""
                try:
                    await sts_msg.edit(progress_text)
                    broadcast_handler.last_update_time = current_time
                except FloodWait as e:
                    logger.warning(f"FloodWait on progress update: {e.value}s")
                    await asyncio.sleep(e.value)
                    try:
                        await sts_msg.edit(progress_text)
                        broadcast_handler.last_update_time = time.time()
                    except Exception:
                        pass
                except Exception as ex:
                    logger.error(f"Error updating progress: {ex}")
                    pass
    
    # Final summary
    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    final_text = f"""
✅ <b>Broadcast Completed!</b>

⏱️ <b>Completed in:</b> <code>{completed_in}</code>

📊 <b>Total Users:</b> {total_users}
✅ <b>Successful:</b> {success}
❌ <b>Failed:</b> {failed}
🚫 <b>Blocked:</b> {blocked}
💤 <b>Deactivated:</b> {deactivated}
⏰ <b>FloodWait Errors:</b> {flood_errors}

📈 <b>Success Rate:</b> <code>{(success/total_users * 100):.2f}%</code>
"""
    
    # Add cleanup button
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ Cleanup Inactive Users", callback_data="cleanup_users")]
    ])
    
    try:
        await sts_msg.edit(final_text, reply_markup=keyboard)
    except FloodWait as e:
        logger.warning(f"FloodWait on final update: {e.value}s")
        await asyncio.sleep(e.value)
        try:
            await sts_msg.edit(final_text, reply_markup=keyboard)
        except Exception:
            pass
    except Exception as ex:
        logger.error(f"Error updating final summary: {ex}")


# =================== ALTERNATIVE BROADCAST (Without Reply) ===================

@Client.on_message(filters.command("broadcasttext") & filters.user(ADMINS))
async def broadcast_text_handler(bot: Client, m: Message):
    """
    Alternative broadcast method - send text directly without reply
    Usage: /broadcasttext Your message here
    """
    if len(m.command) < 2:
        return await m.reply("❌ <b>Usage:</b> <code>/broadcasttext Your message here</code>")
    
    # Extract message text
    broadcast_text = m.text.split(None, 1)[1]
    
    all_users = await db.get_all_active_users()
    sts_msg = await m.reply_text("🚀 <b>Broadcasting Message...</b>", parse_mode=ParseMode.HTML)
    
    done = 0
    success = 0
    failed = 0
    start_time = time.time()
    total_users = await db.total_users_count()
    
    async for user in all_users:
        user_id = user['_id']
        try:
            await bot.send_message(chat_id=user_id, text=broadcast_text)
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await bot.send_message(chat_id=user_id, text=broadcast_text)
                success += 1
            except Exception:
                failed += 1
        except (UserIsBlocked, InputUserDeactivated, PeerIdInvalid):
            await db.mark_user_blocked(user_id)
            failed += 1
        except Exception as e:
            logger.error(f"Broadcast error for {user_id}: {e}")
            failed += 1
        
        done += 1
        
        # Update progress every 100 users with time gap to avoid FloodWait
        if done % 100 == 0:
            current_time = time.time()
            if not hasattr(broadcast_text_handler, 'last_update_time'):
                broadcast_text_handler.last_update_time = 0
            
            if current_time - broadcast_text_handler.last_update_time >= 3:
                try:
                    await sts_msg.edit(f"📊 Progress: {done}/{total_users}\n✅ Success: {success} | ❌ Failed: {failed}")
                    broadcast_text_handler.last_update_time = current_time
                except FloodWait as e:
                    logger.warning(f"FloodWait on progress update: {e.value}s")
                    await asyncio.sleep(e.value)
                except Exception:
                    pass
    
    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    try:
        await sts_msg.edit(f"✅ <b>Broadcast Complete!</b>\n\n⏱️ Time: <code>{completed_in}</code>\n✅ Success: {success}\n❌ Failed: {failed}")
    except FloodWait as e:
        logger.warning(f"FloodWait on final update: {e.value}s")
        await asyncio.sleep(e.value)
        try:
            await sts_msg.edit(f"✅ <b>Broadcast Complete!</b>\n\n⏱️ Time: <code>{completed_in}</code>\n✅ Success: {success}\n❌ Failed: {failed}")
        except Exception:
            pass
    except Exception:
        pass


# =================== SEND MESSAGE FUNCTION ===================

async def send_msg(user_id, message):
    """
    Enhanced send message function with detailed error tracking
    Returns: (status_code, error_type)
    """
    try:
        await message.copy(chat_id=int(user_id))
        return 200, None
        
    except FloodWait as e:
        logger.warning(f"FloodWait {e.value}s for user {user_id}")
        await asyncio.sleep(e.value)
        # Retry after waiting
        try:
            await message.copy(chat_id=int(user_id))
            return 200, None
        except Exception:
            return 429, 'flood'
            
    except InputUserDeactivated:
        logger.info(f"{user_id}: Account deactivated")
        return 400, 'deactivated'
        
    except UserIsBlocked:
        logger.info(f"{user_id}: Blocked the bot")
        return 400, 'blocked'
        
    except PeerIdInvalid:
        logger.info(f"{user_id}: Invalid user ID")
        return 400, 'invalid'
        
    except ChatWriteForbidden:
        logger.info(f"{user_id}: Chat write forbidden")
        return 400, 'blocked'
        
    except Exception as e:
        logger.error(f"{user_id}: {type(e).__name__} - {e}")
        return 500, 'unknown'


# =================== CLEANUP COMMAND ===================

@Client.on_message(filters.command("cleanup") & filters.user(ADMINS))
async def cleanup_users_command(bot: Client, message: Message):
    """Remove blocked and deactivated users from database"""
    msg = await message.reply("🗑️ <b>Cleaning up inactive users...</b>")
    
    deleted_count = await db.cleanup_inactive_users()
    
    await msg.edit(f"✅ <b>Cleanup Complete!</b>\n\n🗑️ Removed: <code>{deleted_count}</code> inactive users")


# =================== CALLBACK QUERY HANDLER ===================

@Client.on_callback_query(filters.regex("cleanup_users"))
async def cleanup_callback(bot: Client, query):
    """Handle cleanup button callback"""
    if query.from_user.id not in ADMINS:
        return await query.answer("⚠️ Only admins can use this!", show_alert=True)
    
    await query.answer("🗑️ Cleaning up...")
    
    deleted_count = await db.cleanup_inactive_users()
    
    await query.message.edit(
        f"{query.message.text}\n\n🗑️ <b>Cleaned up:</b> <code>{deleted_count}</code> inactive users"
    )


# =================== PING COMMAND ===================

@Client.on_message(filters.command("ping") & filters.user(ADMINS))
async def ping_handler(bot: Client, message: Message):
    """Check bot response time"""
    start = time.time()
    msg = await message.reply("🏓 Pinging...")
    end = time.time()
    
    await msg.edit(f"🏓 <b>Pong!</b>\n⏱️ Response Time: <code>{(end-start)*1000:.2f}ms</code>")


# =================== GROUP BROADCAST ===================

@Client.on_message(filters.command("groupbroadcast") & filters.user(ADMINS) & filters.reply)
async def grp_brodcst(bot, message):
    """
    Alternative group broadcast using chat_db
    Reply to a message with /groupbroadcast
    """
    chats = await chat_db.get_all_chats()
    b_msg = message.reply_to_message
    sts = await message.reply_text(
        text='Broadcasting your messages to groups...'
    )
    start_time = time.time()
    total_chats = len(chats)
    done = 0
    blocked = 0
    deleted = 0
    failed = 0
    success = 0
    
    for chat in chats:
        try:
            # Get chat id - handle both 'id' and 'chat_id' keys
            chat_id = chat.get('id') or chat.get('chat_id')
            if not chat_id:
                failed += 1
                continue
                
            # Try to copy message to chat
            await b_msg.copy(chat_id=int(chat_id))
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await b_msg.copy(chat_id=int(chat_id))
                success += 1
            except Exception:
                failed += 1
        except (ChatWriteForbidden, UserNotParticipant):
            blocked += 1
        except Exception as e:
            logger.error(f"Error broadcasting to chat {chat_id}: {e}")
            failed += 1
        
        done += 1
        await asyncio.sleep(2)
        
        # Update progress every 20 chats with time gap to avoid FloodWait
        if done % 20 == 0:
            current_time = time.time()
            if not hasattr(grp_brodcst, 'last_update_time'):
                grp_brodcst.last_update_time = 0
            
            if current_time - grp_brodcst.last_update_time >= 3:
                try:
                    await sts.edit(
                        f"Broadcast in progress:\n\n"
                        f"Total Chats: {total_chats}\n"
                        f"Completed: {done} / {total_chats}\n"
                        f"Success: {success}\n"
                        f"Blocked: {blocked}\n"
                        f"Failed: {failed}"
                    )
                    grp_brodcst.last_update_time = current_time
                except FloodWait as e:
                    logger.warning(f"FloodWait on progress update: {e.value}s")
                    await asyncio.sleep(e.value)
                except Exception:
                    pass
    
    # Final update
    time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
    try:
        await sts.edit(
            f"Broadcast Completed:\n"
            f"Completed in {time_taken} seconds.\n\n"
            f"Total Chats: {total_chats}\n"
            f"Completed: {done} / {total_chats}\n"
            f"Success: {success}\n"
            f"Blocked: {blocked}\n"
            f"Failed: {failed}"
        )
    except FloodWait as e:
        logger.warning(f"FloodWait on final update: {e.value}s")
        await asyncio.sleep(e.value)
        try:
            await sts.edit(
                f"Broadcast Completed:\n"
                f"Completed in {time_taken} seconds.\n\n"
                f"Total Chats: {total_chats}\n"
                f"Completed: {done} / {total_chats}\n"
                f"Success: {success}\n"
                f"Blocked: {blocked}\n"
                f"Failed: {failed}"
            )
        except Exception:
            pass
    except Exception:
        pass


@Client.on_message(filters.command("groupcount") & filters.user(ADMINS))
async def group_count_handler(bot: Client, message: Message):
    """Get count of groups from database"""
    msg = await message.reply_text("📊 Counting groups...")
    
    total_groups = await db.total_groups_count()
    active_groups = await db.active_groups_count()
    inactive_groups = total_groups - active_groups
    
    text = f"""
📊 <b>GROUP STATISTICS</b>

📈 <b>Total Groups:</b> <code>{total_groups}</code>
✅ <b>Active Groups:</b> <code>{active_groups}</code>
❌ <b>Inactive Groups:</b> <code>{inactive_groups}</code>

ℹ️ Groups are tracked when bot joins them
"""
    
    await msg.edit(text)


# =================== AUTO-TRACK GROUPS ===================

@Client.on_message(filters.group & filters.new_chat_members)
async def track_new_group(bot: Client, message: Message):
    """Automatically track when bot is added to a group"""
    # Check if bot was added
    for member in message.new_chat_members:
        if member.id == bot.me.id:
            # Bot was added to this group
            chat_id = message.chat.id
            chat_title = message.chat.title
            
            await db.add_group(chat_id, chat_title)
            logger.info(f"Bot added to group: {chat_title} ({chat_id})")
            
            # Send welcome message to group
            try:
                await message.reply_text(
                    f"👋 <b>Hello {chat_title}!</b>\n\n"
                    "Thank you for adding me to your group!\n"
                    "I'm now ready to serve you."
                )
            except:
                pass
            break


@Client.on_message(filters.group & filters.left_chat_member)
async def track_left_group(bot: Client, message: Message):
    """Track when bot leaves or is removed from a group"""
    # Check if bot left
    if message.left_chat_member.id == bot.me.id:
        chat_id = message.chat.id
        
        await db.remove_group(chat_id)
        logger.info(f"Bot removed from group: {chat_id}")
