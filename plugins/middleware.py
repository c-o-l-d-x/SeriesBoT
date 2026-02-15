import logging
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from database.chat_db import chat_db
from info import ADMINS

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# =================== MIDDLEWARE FOR BANNED USERS AND DISABLED CHATS ===================

@Client.on_message(filters.incoming & ~filters.service, group=-1)
async def check_banned_and_disabled(client: Client, message: Message):
    """
    Global middleware to check if user is banned or chat is disabled
    This runs before all other message handlers (group=-1)
    """
    # Check if user is banned (applies to everyone except admins)
    if message.from_user:
        # Admins are exempt from ban checks
        if message.from_user.id not in ADMINS:
            is_banned = await chat_db.is_user_banned(message.from_user.id)
            if is_banned:
                logger.info(f"Blocked message from banned user: {message.from_user.id}")
                # Silently ignore - don't respond to banned users
                message.stop_propagation()
                return
    
    # Check if chat is disabled (for groups/supergroups)
    # This applies to EVERYONE including admins, except for enable/disable commands
    if message.chat.type in ["group", "supergroup"]:
        # Allow enable/disable commands to work even in disabled chats
        # so admins can re-enable disabled chats
        if message.text and message.text.startswith('/'):
            command = message.text.split()[0].lower()
            if command in ['/enable', '/disable']:
                # Let enable/disable commands pass through
                return
        
        is_disabled = await chat_db.is_chat_disabled(message.chat.id)
        if is_disabled:
            logger.info(f"Blocked message from disabled chat: {message.chat.id}")
            # Silently ignore - don't respond in disabled chats
            message.stop_propagation()
            return


@Client.on_callback_query(group=-1)
async def check_banned_callback(client: Client, query: CallbackQuery):
    """
    Global middleware to check if user is banned for callback queries
    This runs before all other callback handlers (group=-1)
    """
    # Check if user is banned (applies to everyone except admins)
    if query.from_user.id not in ADMINS:
        is_banned = await chat_db.is_user_banned(query.from_user.id)
        if is_banned:
            logger.info(f"Blocked callback from banned user: {query.from_user.id}")
            await query.answer("⛔ You are banned from using this bot!", show_alert=True)
            query.stop_propagation()
            return
    
    # Check if chat is disabled (for groups/supergroups)
    # This applies to EVERYONE including admins
    if query.message.chat.type in ["group", "supergroup"]:
        is_disabled = await chat_db.is_chat_disabled(query.message.chat.id)
        if is_disabled:
            logger.info(f"Blocked callback from disabled chat: {query.message.chat.id}")
            await query.answer("⛔ Bot is disabled in this chat!", show_alert=True)
            query.stop_propagation()
            return
