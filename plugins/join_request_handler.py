"""
Chat Join Request Handler
Automatically adds users to database when they request to join the channel
"""
from pyrogram import Client, filters
from pyrogram.types import ChatJoinRequest
from database.force_sub_db import force_sub_db
import logging

logger = logging.getLogger(__name__)


@Client.on_chat_join_request()
async def handle_join_request(client: Client, join_request: ChatJoinRequest):
    """
    Handle join requests to force sub channel
    Automatically adds user to authorized users database
    """
    try:
        # Get force sub settings
        settings = await force_sub_db.get_settings()
        
        if not settings or not settings.get('enabled', False):
            return
        
        channel_id = settings.get('channel_id')
        mode = settings.get('mode', 'request')
        
        # Only process if it's the force sub channel and in request mode
        if join_request.chat.id == channel_id and mode == "request":
            user_id = join_request.from_user.id
            first_name = join_request.from_user.first_name
            username = join_request.from_user.username
            join_date = join_request.date
            
            # Add user to database
            success = await force_sub_db.add_user(
                user_id=user_id,
                first_name=first_name,
                username=username,
                join_date=join_date
            )
            
            if success:
                logger.info(f"User {user_id} ({first_name}) requested to join and was added to database")
            else:
                logger.error(f"Failed to add user {user_id} to database")
                
    except Exception as e:
        logger.error(f"Error handling join request: {e}", exc_info=True)


@Client.on_chat_member_updated()
async def handle_chat_member_update(client: Client, chat_member_updated):
    """
    Handle when user joins the channel (for normal force sub mode)
    Automatically adds user to authorized users database
    """
    try:
        # Get force sub settings
        settings = await force_sub_db.get_settings()
        
        if not settings or not settings.get('enabled', False):
            return
        
        channel_id = settings.get('channel_id')
        mode = settings.get('mode', 'request')
        
        # Only process if it's the force sub channel and in normal mode
        if chat_member_updated.chat.id != channel_id:
            return
        
        # Check if user joined (old status was not member, new status is member)
        old_status = chat_member_updated.old_chat_member.status if chat_member_updated.old_chat_member else None
        new_status = chat_member_updated.new_chat_member.status
        
        from pyrogram.enums import ChatMemberStatus
        
        # User joined
        if old_status in [None, ChatMemberStatus.LEFT, ChatMemberStatus.RESTRICTED] and \
           new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            
            user = chat_member_updated.new_chat_member.user
            user_id = user.id
            first_name = user.first_name
            username = user.username
            
            # Add user to database
            success = await force_sub_db.add_user(
                user_id=user_id,
                first_name=first_name,
                username=username
            )
            
            if success:
                logger.info(f"User {user_id} ({first_name}) joined channel and was added to database")
            else:
                logger.error(f"Failed to add user {user_id} to database")
        
        # User left - optionally remove from database
        elif old_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER] and \
             new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
            
            user = chat_member_updated.old_chat_member.user
            user_id = user.id
            
            # Optionally remove user from database when they leave
            # Uncomment the line below if you want to remove users when they leave
            # await force_sub_db.delete_user(user_id)
            
            logger.info(f"User {user_id} left/was banned from channel")
                
    except Exception as e:
        logger.error(f"Error handling chat member update: {e}", exc_info=True)
