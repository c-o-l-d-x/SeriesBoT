"""
Update Channel Module
Manages automatic posting and updating of series information to an update channel.
"""

import logging
from pyrogram import Client
from pyrogram.errors import FloodWait
from database.series_db import db
from info import UPDATE_CHANNEL
import asyncio

logger = logging.getLogger(__name__)


async def format_series_update_message(series_data):
    """
    Format the series data into an update message.
    
    Args:
        series_data: Dictionary containing series information
    
    Returns:
        str: Formatted HTML message
    """
    title = series_data.get('title', 'Unknown Series')
    year = series_data.get('year', '')
    
    # Start with series name and year
    message = f"<code>{title}"
    if year:
        message += f" ({year})"
    message += "</code>\n\n"
    
    languages = series_data.get('languages', {})
    
    if not languages:
        return message + "<i>No content available yet.</i>"
    
    # Group by language
    for lang_id, lang_data in languages.items():
        lang_name = lang_data.get('name', 'Unknown')
        seasons = lang_data.get('seasons', {})
        
        # Check if language has any published content
        has_published_content = False
        season_info = []
        
        for season_id, season_data in seasons.items():
            season_name = season_data.get('name', 'Unknown')
            qualities = season_data.get('qualities', {})
            
            # Get published qualities
            published_qualities = []
            for quality_id, quality_data in qualities.items():
                if quality_data.get('published', False) and quality_data.get('batch_link'):
                    quality_name = quality_data.get('name', 'Unknown')
                    published_qualities.append(quality_name)
            
            if published_qualities:
                has_published_content = True
                # Format: S01 : 720p.H.265, 1080p.H.265
                qualities_str = ", ".join(published_qualities)
                season_info.append(f"{season_name} : {qualities_str}")
        
        # Only add language section if it has published content
        if has_published_content:
            message += f"<b>Language : {lang_name}</b>\n"
            message += "\n".join(season_info)
            message += "\n\n"
    
    # Remove trailing newlines
    message = message.rstrip()
    
    # If no published content found
    if message.endswith("</code>\n"):
        message += "\n<i>No content available yet.</i>"
    
    return message


async def send_or_update_series_message(client: Client, series_id: str):
    """
    Send a new update message or update existing one for a series.
    
    Args:
        client: Pyrogram client instance
        series_id: Series ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not UPDATE_CHANNEL:
        logger.warning("UPDATE_CHANNEL not configured")
        return False
    
    try:
        # Get series data
        series = await db.get_series(series_id)
        if not series:
            logger.error(f"Series {series_id} not found")
            return False
        
        # Check if series is published
        if not series.get('published', False):
            logger.info(f"Series {series_id} is not published, skipping update message")
            return True  # Not an error, just skip
        
        # Format the message
        message_text = await format_series_update_message(series)
        
        # Check if update message already exists
        update_msg_id = series.get('update_message_id')
        
        if update_msg_id:
            # Update existing message
            try:
                await client.edit_message_text(
                    chat_id=UPDATE_CHANNEL,
                    message_id=update_msg_id,
                    text=message_text
                )
                logger.info(f"Updated series message for {series.get('title')} (ID: {update_msg_id})")
                return True
            except Exception as e:
                logger.error(f"Failed to edit message {update_msg_id}: {e}")
                # Message might have been deleted, create new one
                update_msg_id = None
        
        if not update_msg_id:
            # Send new message
            try:
                sent_message = await client.send_message(
                    chat_id=UPDATE_CHANNEL,
                    text=message_text
                )
                
                # Store the message ID in database
                await db.set_update_message_id(series_id, sent_message.id)
                logger.info(f"Sent new update message for {series.get('title')} (ID: {sent_message.id})")
                return True
            except FloodWait as e:
                logger.warning(f"FloodWait: Waiting {e.value} seconds")
                await asyncio.sleep(e.value)
                return await send_or_update_series_message(client, series_id)
            except Exception as e:
                logger.error(f"Failed to send update message: {e}")
                return False
    
    except Exception as e:
        logger.error(f"Error in send_or_update_series_message: {e}", exc_info=True)
        return False


async def delete_series_update_message(client: Client, series_id: str):
    """
    Delete the update message for a series.
    
    Args:
        client: Pyrogram client instance
        series_id: Series ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not UPDATE_CHANNEL:
        logger.warning("UPDATE_CHANNEL not configured")
        return False
    
    try:
        # Get series data
        series = await db.get_series(series_id)
        if not series:
            logger.error(f"Series {series_id} not found")
            return False
        
        # Get update message ID
        update_msg_id = series.get('update_message_id')
        
        if update_msg_id:
            try:
                await client.delete_messages(
                    chat_id=UPDATE_CHANNEL,
                    message_ids=update_msg_id
                )
                logger.info(f"Deleted update message {update_msg_id} for {series.get('title')}")
                
                # Clear the message ID from database
                await db.set_update_message_id(series_id, None)
                return True
            except Exception as e:
                logger.error(f"Failed to delete message {update_msg_id}: {e}")
                return False
        else:
            logger.info(f"No update message to delete for series {series_id}")
            return True
    
    except Exception as e:
        logger.error(f"Error in delete_series_update_message: {e}", exc_info=True)
        return False
