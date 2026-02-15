import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    ChatAdminRequired,
    UserNotParticipant,
    ChannelPrivate,
    PeerIdInvalid
)
from info import ADMINS
from database.chat_db import chat_db

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# =================== BAN USER ===================

@Client.on_message(filters.command("ban") & filters.user(ADMINS))
async def ban_user(client: Client, message: Message):
    """
    Ban a user from using the bot
    Usage: /ban user_id
    Reply to user: /ban
    """
    user_id = None
    
    # Check if replying to a user
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    # Check if user_id provided in command
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
        except ValueError:
            await message.reply_text("❌ Invalid user ID!")
            return
    else:
        await message.reply_text("⚠️ <b>Usage:</b>\n<code>/ban user_id</code> or reply to user with <code>/ban</code>", parse_mode=ParseMode.HTML)
        return
    
    # Don't allow banning admins
    if user_id in ADMINS:
        await message.reply_text("❌ Cannot ban an admin!")
        return
    
    # Ban user
    success = await chat_db.ban_user(user_id)
    
    if success:
        await message.reply_text(f"✅ User <code>{user_id}</code> has been banned from using the bot!", parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(f"❌ Failed to ban user <code>{user_id}</code>!", parse_mode=ParseMode.HTML)


# =================== UNBAN USER ===================

@Client.on_message(filters.command("unban") & filters.user(ADMINS))
async def unban_user(client: Client, message: Message):
    """
    Unban a user
    Usage: /unban user_id
    Reply to user: /unban
    """
    user_id = None
    
    # Check if replying to a user
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    # Check if user_id provided in command
    elif len(message.command) > 1:
        try:
            user_id = int(message.command[1])
        except ValueError:
            await message.reply_text("❌ Invalid user ID!")
            return
    else:
        await message.reply_text("⚠️ <b>Usage:</b>\n<code>/unban user_id</code> or reply to user with <code>/unban</code>", parse_mode=ParseMode.HTML)
        return
    
    # Unban user
    success = await chat_db.unban_user(user_id)
    
    if success:
        await message.reply_text(f"✅ User <code>{user_id}</code> has been unbanned!", parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(f"❌ Failed to unban user <code>{user_id}</code>!", parse_mode=ParseMode.HTML)


# =================== BANNED USERS LIST ===================

@Client.on_message(filters.command("banned") & filters.user(ADMINS))
async def banned_users(client: Client, message: Message):
    """Get list of all banned users"""
    msg = await message.reply_text("📋 Fetching banned users...")
    
    banned_list = await chat_db.get_banned_users()
    
    if not banned_list:
        await msg.edit("✅ No banned users found!")
        return
    
    text = "🚫 <b>BANNED USERS LIST</b>\n\n"
    for user in banned_list:
        text += f"• <code>{user['user_id']}</code>\n"
    
    text += f"\n<b>Total:</b> {len(banned_list)} users"
    
    await msg.edit(text)


# =================== ENABLE CHAT ===================

@Client.on_message(filters.command("enable") & filters.user(ADMINS))
async def enable_chat(client: Client, message: Message):
    """
    Enable bot in a chat
    Usage: /enable chat_id
    In group: /enable
    """
    chat_id = None
    
    # If used in group
    if message.chat.type in ["group", "supergroup"]:
        chat_id = message.chat.id
    # If chat_id provided
    elif len(message.command) > 1:
        try:
            chat_id = int(message.command[1])
        except ValueError:
            await message.reply_text("❌ Invalid chat ID!")
            return
    else:
        await message.reply_text("⚠️ <b>Usage:</b>\n<code>/enable</code> in group or <code>/enable chat_id</code>", parse_mode=ParseMode.HTML)
        return
    
    # Enable chat
    success = await chat_db.enable_chat(chat_id)
    
    if success:
        await message.reply_text(f"✅ Bot enabled for chat <code>{chat_id}</code>!", parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(f"❌ Failed to enable chat <code>{chat_id}</code>!", parse_mode=ParseMode.HTML)


# =================== DISABLE CHAT ===================

@Client.on_message(filters.command("disable") & filters.user(ADMINS))
async def disable_chat(client: Client, message: Message):
    """
    Disable bot in a chat
    Usage: /disable chat_id
    In group: /disable
    """
    chat_id = None
    
    # If used in group
    if message.chat.type in ["group", "supergroup"]:
        chat_id = message.chat.id
    # If chat_id provided
    elif len(message.command) > 1:
        try:
            chat_id = int(message.command[1])
        except ValueError:
            await message.reply_text("❌ Invalid chat ID!")
            return
    else:
        await message.reply_text("⚠️ <b>Usage:</b>\n<code>/disable</code> in group or <code>/disable chat_id</code>", parse_mode=ParseMode.HTML)
        return
    
    # Disable chat
    success = await chat_db.disable_chat(chat_id)
    
    if success:
        await message.reply_text(f"🔴 Bot disabled for chat <code>{chat_id}</code>!", parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(f"❌ Failed to disable chat <code>{chat_id}</code>!", parse_mode=ParseMode.HTML)


# =================== CHAT STATUS ===================

@Client.on_message(filters.command("chatstatus") & filters.user(ADMINS))
async def chat_status(client: Client, message: Message):
    """Get status of all chats"""
    msg = await message.reply_text("📋 Fetching chat status...")
    
    enabled_chats = await chat_db.get_enabled_chats()
    disabled_chats = await chat_db.get_disabled_chats()
    
    text = "📊 <b>CHAT STATUS</b>\n\n"
    
    text += f"✅ <b>Enabled Chats:</b> {len(enabled_chats)}\n"
    for chat in enabled_chats[:10]:  # Show first 10
        text += f"  • <code>{chat['chat_id']}</code>\n"
    
    text += f"\n🔴 <b>Disabled Chats:</b> {len(disabled_chats)}\n"
    for chat in disabled_chats[:10]:  # Show first 10
        text += f"  • <code>{chat['chat_id']}</code>\n"
    
    await msg.edit(text)


# =================== LEAVE CHAT ===================

@Client.on_message(filters.command("leave") & filters.user(ADMINS))
async def leave_chat_cmd(client: Client, message: Message):
    """
    Make bot leave a chat
    Usage: /leave chat_id
    In group: /leave
    """
    chat_id = None
    
    # If used in group
    if message.chat.type in ["group", "supergroup"]:
        chat_id = message.chat.id
        confirm_msg = await message.reply_text(
            "⚠️ Are you sure you want me to leave this chat?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes, Leave", callback_data=f"leave_confirm_{chat_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="leave_cancel")
                ]
            ])
        )
        return
    
    # If chat_id provided
    elif len(message.command) > 1:
        try:
            chat_id = int(message.command[1])
        except ValueError:
            await message.reply_text("❌ Invalid chat ID!")
            return
    else:
        await message.reply_text("⚠️ <b>Usage:</b>\n<code>/leave</code> in group or <code>/leave chat_id</code>", parse_mode=ParseMode.HTML)
        return
    
    # Leave chat directly if chat_id provided
    try:
        await client.leave_chat(chat_id)
        await message.reply_text(f"✅ Successfully left chat <code>{chat_id}</code>!", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error leaving chat {chat_id}: {e}")
        await message.reply_text(f"❌ Failed to leave chat <code>{chat_id}</code>!\nError: {str(e)}", parse_mode=ParseMode.HTML)


# =================== LEAVE CALLBACK ===================

@Client.on_callback_query(filters.regex("leave_"))
async def leave_callback(client: Client, query):
    """Handle leave chat callback"""
    if query.from_user.id not in ADMINS:
        return await query.answer("⚠️ Only admins can use this!", show_alert=True)
    
    data = query.data
    
    if data == "leave_cancel":
        await query.message.delete()
        await query.answer("❌ Leave cancelled!")
        return
    
    if data.startswith("leave_confirm_"):
        chat_id = int(data.replace("leave_confirm_", ""))
        
        try:
            await query.message.edit_text("👋 Goodbye! Leaving chat...")
            await client.leave_chat(chat_id)
            # This won't be sent since bot already left
        except Exception as e:
            logger.error(f"Error leaving chat {chat_id}: {e}")
            await query.message.edit_text(f"❌ Failed to leave!\nError: {str(e)}")


# =================== GET INVITE LINK ===================

@Client.on_message(filters.command("invitelink") & filters.user(ADMINS))
async def get_invite_link(client: Client, message: Message):
    """
    Get invite link for a chat where bot is admin
    Usage: /invitelink chat_id
    In group: /invitelink
    """
    chat_id = None
    
    # If used in group
    if message.chat.type in ["group", "supergroup"]:
        chat_id = message.chat.id
    # If chat_id provided
    elif len(message.command) > 1:
        try:
            chat_id = int(message.command[1])
        except ValueError:
            await message.reply_text("❌ Invalid chat ID!")
            return
    else:
        await message.reply_text("⚠️ <b>Usage:</b>\n<code>/invitelink</code> in group or <code>/invitelink chat_id</code>", parse_mode=ParseMode.HTML)
        return
    
    msg = await message.reply_text("🔗 Generating invite link...")
    
    try:
        # Get chat
        chat = await client.get_chat(chat_id)
        
        # Check if bot is admin
        bot_member = await client.get_chat_member(chat_id, "me")
        
        if not bot_member.privileges or not bot_member.privileges.can_invite_users:
            await msg.edit("❌ Bot is not admin or doesn't have permission to invite users!")
            return
        
        # Export invite link
        invite_link = await client.export_chat_invite_link(chat_id)
        
        text = f"🔗 <b>INVITE LINK</b>\n\n"
        text += f"<b>Chat:</b> {chat.title}\n"
        text += f"<b>Chat ID:</b> <code>{chat_id}</code>\n\n"
        text += f"<b>Link:</b> {invite_link}"
        
        await msg.edit(text)
        
    except ChatAdminRequired:
        await msg.edit("❌ Bot is not admin in this chat!")
    except ChannelPrivate:
        await msg.edit("❌ This chat is private or bot is not a member!")
    except PeerIdInvalid:
        await msg.edit("❌ Invalid chat ID!")
    except Exception as e:
        logger.error(f"Error getting invite link for {chat_id}: {e}")
        await msg.edit(f"❌ Error: {str(e)}")


# =================== GET CHAT INFO ===================

@Client.on_message(filters.command("chatinfo") & filters.user(ADMINS))
async def get_chat_info(client: Client, message: Message):
    """
    Get detailed information about a chat
    Usage: /chatinfo chat_id
    In group: /chatinfo
    """
    chat_id = None
    
    # If used in group
    if message.chat.type in ["group", "supergroup"]:
        chat_id = message.chat.id
    # If chat_id provided
    elif len(message.command) > 1:
        try:
            chat_id = int(message.command[1])
        except ValueError:
            await message.reply_text("❌ Invalid chat ID!")
            return
    else:
        await message.reply_text("⚠️ <b>Usage:</b>\n<code>/chatinfo</code> in group or <code>/chatinfo chat_id</code>", parse_mode=ParseMode.HTML)
        return
    
    msg = await message.reply_text("📋 Fetching chat info...")
    
    try:
        chat = await client.get_chat(chat_id)
        
        text = f"📊 <b>CHAT INFORMATION</b>\n\n"
        text += f"<b>Title:</b> {chat.title}\n"
        text += f"<b>Chat ID:</b> <code>{chat.id}</code>\n"
        text += f"<b>Type:</b> {chat.type}\n"
        
        if chat.username:
            text += f"<b>Username:</b> @{chat.username}\n"
        
        if chat.members_count:
            text += f"<b>Members:</b> {chat.members_count}\n"
        
        if chat.description:
            text += f"<b>Description:</b> {chat.description[:100]}...\n"
        
        # Check bot status
        try:
            bot_member = await client.get_chat_member(chat_id, "me")
            text += f"\n<b>Bot Status:</b> {bot_member.status}\n"
            
            if bot_member.privileges:
                text += f"<b>Is Admin:</b> Yes\n"
                text += f"<b>Can Invite:</b> {bot_member.privileges.can_invite_users}\n"
                text += f"<b>Can Delete:</b> {bot_member.privileges.can_delete_messages}\n"
            else:
                text += f"<b>Is Admin:</b> No\n"
        except:
            text += f"\n<b>Bot Status:</b> Unknown\n"
        
        await msg.edit(text)
        
    except ChannelPrivate:
        await msg.edit("❌ This chat is private or bot is not a member!")
    except PeerIdInvalid:
        await msg.edit("❌ Invalid chat ID!")
    except Exception as e:
        logger.error(f"Error getting chat info for {chat_id}: {e}")
        await msg.edit(f"❌ Error: {str(e)}")
