"""
Force Subscribe Handler
Handles force subscribe checks for both request and normal modes
"""
import asyncio
from pyrogram import Client
from pyrogram.errors import FloodWait, UserNotParticipant, ChatAdminRequired, PeerIdInvalid
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatMemberStatus
from database.force_sub_db import force_sub_db
from info import ADMINS
import logging

logger = logging.getLogger(__name__)

# Global invite link cache
INVITE_LINK_CACHE = {}


async def get_invite_link(client: Client, channel_id: int, mode: str = "request"):
    """
    Get or create invite link for the force sub channel
    
    Args:
        client: Pyrogram client
        channel_id: Channel ID
        mode: "request" for join request mode, "normal" for instant join
    
    Returns:
        Invite link string or None if failed
    """
    global INVITE_LINK_CACHE
    
    # Check cache first
    cache_key = f"{channel_id}_{mode}"
    if cache_key in INVITE_LINK_CACHE:
        return INVITE_LINK_CACHE[cache_key]
    
    try:
        # Create invite link
        creates_join_request = (mode == "request")
        invite_link_obj = await client.create_chat_invite_link(
            chat_id=channel_id,
            creates_join_request=creates_join_request
        )
        
        invite_link = invite_link_obj.invite_link
        INVITE_LINK_CACHE[cache_key] = invite_link
        
        logger.info(f"Created {mode} invite link for channel {channel_id}")
        return invite_link
        
    except ChatAdminRequired:
        logger.error(f"Bot is not admin in channel {channel_id}")
        return None
    except Exception as e:
        logger.error(f"Error creating invite link: {e}", exc_info=True)
        return None


async def check_force_sub(client: Client, message: Message) -> tuple[bool, str]:
    """
    Check if user should be allowed access based on force sub settings
    
    Args:
        client: Pyrogram client
        message: Message object
    
    Returns:
        Tuple of (is_authorized: bool, error_message: str or None)
    """
    user_id = message.from_user.id
    
    # Admins always have access
    if user_id in ADMINS:
        return True, None
    
    # Get force sub settings
    settings = await force_sub_db.get_settings()
    
    # If force sub is disabled, allow access
    if not settings or not settings.get('enabled', False):
        return True, None
    
    channel_id = settings.get('channel_id')
    if not channel_id:
        logger.error("Force sub enabled but no channel ID set")
        return True, None  # Allow access if misconfigured
    
    mode = settings.get('mode', 'request')
    
    # Check if user is already authorized (in database)
    if await force_sub_db.is_user_authorized(user_id):
        logger.info(f"User {user_id} is already authorized")
        return True, None
    
    # For request mode, check database first
    if mode == "request":
        # User not in database, need to request
        invite_link = await get_invite_link(client, channel_id, mode="request")
        if not invite_link:
            return True, None  # Allow if invite link creation failed
        
        # Get custom message or use default
        force_message = settings.get('force_message') or get_default_force_message()
        
        error_msg = {
            'message': force_message,
            'invite_link': invite_link,
            'mode': 'request'
        }
        return False, error_msg
    
    # For normal mode, check actual membership
    else:
        try:
            # Check if user is a member of the channel
            member = await client.get_chat_member(chat_id=channel_id, user_id=user_id)
            
            if member.status in [ChatMemberStatus.BANNED]:
                return False, {
                    'message': "❌ Sorry, you are banned from the channel.",
                    'invite_link': None,
                    'mode': 'banned'
                }
            
            if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                # User is a member, add to database for future quick checks
                await force_sub_db.add_user(
                    user_id=user_id,
                    first_name=message.from_user.first_name,
                    username=message.from_user.username
                )
                return True, None
            
            # User is not a member
            raise UserNotParticipant("Not a member")
            
        except UserNotParticipant:
            # User needs to join
            invite_link = await get_invite_link(client, channel_id, mode="normal")
            if not invite_link:
                return True, None
            
            force_message = settings.get('force_message') or get_default_force_message()
            
            error_msg = {
                'message': force_message,
                'invite_link': invite_link,
                'mode': 'normal'
            }
            return False, error_msg
        
        except Exception as e:
            logger.error(f"Error checking membership: {e}", exc_info=True)
            return True, None  # Allow access on error


def get_default_force_message():
    """Get default force subscribe message"""
    return """
🔒 <b>Access Restricted</b>

To access this content, you need to join our channel first.

👉 Click the button below to join/request
👉 Then click "Try Again" to get your content

Thank you! 🙏
"""


async def send_force_sub_message(message: Message, error_data: dict, deep_link: str = None):
    """
    Send force subscribe message to user
    
    Args:
        message: Message object
        error_data: Dictionary containing message, invite_link, and mode
        deep_link: Optional deep link to retry after joining
    """
    try:
        mode = error_data.get('mode', 'request')
        invite_link = error_data.get('invite_link')
        force_message = error_data.get('message')
        
        # Create buttons
        buttons = []
        
        if mode == 'banned':
            # No buttons for banned users
            await message.reply_text(force_message)
            return
        
        # Join/Request button
        if mode == 'request':
            button_text = "📨 Send Join Request"
        else:
            button_text = "✅ Join Channel"
        
        if invite_link:
            buttons.append([InlineKeyboardButton(button_text, url=invite_link)])
        
        # Try again button
        if deep_link:
            retry_url = f"https://t.me/{message._client.me.username}?start={deep_link}"
            buttons.append([InlineKeyboardButton("🔄 Try Again", url=retry_url)])
        
        # Send message
        if buttons:
            await message.reply_text(
                force_message,
                reply_markup=InlineKeyboardMarkup(buttons),
                quote=True
            )
        else:
            await message.reply_text(force_message, quote=True)
            
    except Exception as e:
        logger.error(f"Error sending force sub message: {e}", exc_info=True)


def clear_invite_link_cache():
    """Clear the invite link cache (useful when settings change)"""
    global INVITE_LINK_CACHE
    INVITE_LINK_CACHE = {}
    logger.info("Invite link cache cleared")
