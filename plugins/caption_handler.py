"""
Caption Handler Module for UltraSeries Bot
Handles dynamic file caption generation with custom variables
"""

import re
from pyrogram import Client, filters
from pyrogram.types import Message
from info import ADMINS
from database.series_db import db
import logging

logger = logging.getLogger(__name__)

# Default caption template
DEFAULT_CAPTION = "{filename}"


def extract_series_info(caption: str) -> dict:
    """
    Extract series information from the original caption
    Supports patterns like:
    - Series.Name.S01E05.720p.WEB-DL.x264
    - Series Name - S01E05 - 1080p HEVC
    - Series_Name_Season_1_Episode_5_720p
    """
    info = {
        'seriesname': '',
        'season': '',
        'episode': '',
        'quality': '',
        'language': ''
    }
    
    if not caption:
        return info
    
    # Extract Season and Episode (S01E05, s01e05, Season 1 Episode 5, etc.)
    season_episode_patterns = [
        r'[Ss](\d{1,2})[Ee](\d{1,2})',  # S01E05, s01e05
        r'Season\s*(\d{1,2})\s*Episode\s*(\d{1,2})',  # Season 1 Episode 5
        r'Season[_\s](\d{1,2})[_\s]Episode[_\s](\d{1,2})',  # Season_1_Episode_5
    ]
    
    for pattern in season_episode_patterns:
        match = re.search(pattern, caption, re.IGNORECASE)
        if match:
            info['season'] = match.group(1).zfill(2)
            info['episode'] = match.group(2).zfill(2)
            break
    
    # Extract Quality (720p, 1080p, 4K, etc.)
    quality_patterns = [
        r'\b(2160p|4K|1080p|720p|480p|360p)\b',
        r'\b(UHD|FHD|HD|SD)\b',
        r'\b(\d{3,4}p)\b'
    ]
    
    for pattern in quality_patterns:
        match = re.search(pattern, caption, re.IGNORECASE)
        if match:
            info['quality'] = match.group(1)
            break
    
    # Look for codec info to enhance quality (H.264, H.265, HEVC, x264, x265)
    codec_match = re.search(r'\b(H\.?26[45]|HEVC|x26[45]|AVC)\b', caption, re.IGNORECASE)
    if codec_match and info['quality']:
        info['quality'] = f"{info['quality']}.{codec_match.group(1)}"
    elif codec_match:
        info['quality'] = codec_match.group(1)
    
    # Extract Language (English, Hindi, Tamil, Telugu, etc.)
    language_patterns = [
        r'\b(English|Hindi|Tamil|Telugu|Malayalam|Kannada|Bengali|Punjabi|Marathi)\b',
        r'\b(Dual\s*Audio|Multi\s*Audio)\b',
        r'\b(ENG|HIN|TAM|TEL|MAL)\b'
    ]
    
    for pattern in language_patterns:
        match = re.search(pattern, caption, re.IGNORECASE)
        if match:
            info['language'] = match.group(1)
            break
    
    # Extract Series Name - remove season/episode and quality info
    series_name = caption
    
    # Remove season/episode pattern
    series_name = re.sub(r'[Ss]\d{1,2}[Ee]\d{1,2}', '', series_name)
    series_name = re.sub(r'Season\s*\d{1,2}\s*Episode\s*\d{1,2}', '', series_name, flags=re.IGNORECASE)
    
    # Remove quality, codec, and other technical terms
    technical_terms = [
        r'\b(2160p|4K|1080p|720p|480p|360p|UHD|FHD|HD|SD)\b',
        r'\b(H\.?26[45]|HEVC|x26[45]|AVC|WEB-DL|WEBRip|BluRay|BRRip|HDRip|DVDRip)\b',
        r'\b(AAC|AC3|DDP|DD|Atmos|TrueHD|DTS|MP3)\b',
        r'\b(10bit|8bit|5\.1|2\.0)\b',
        r'\b(English|Hindi|Tamil|Telugu|Malayalam|Kannada|Bengali|Punjabi|Marathi)\b',
        r'\b(Dual\s*Audio|Multi\s*Audio)\b',
        r'\b(ENG|HIN|TAM|TEL|MAL)\b',
        r'\b(PROPER|REPACK|INTERNAL|LIMITED)\b',
        r'\b(NF|AMZN|DSNP|HULU|HMAX|SHO|ATVP)\b'
    ]
    
    for term in technical_terms:
        series_name = re.sub(term, '', series_name, flags=re.IGNORECASE)
    
    # Clean up: replace dots/underscores with spaces, remove extra spaces
    series_name = series_name.replace('.', ' ').replace('_', ' ').replace('-', ' ')
    series_name = re.sub(r'\s+', ' ', series_name).strip()
    
    # Remove leading/trailing special characters
    series_name = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', series_name).strip()
    
    info['seriesname'] = series_name if series_name else ''
    
    return info


def format_caption(template: str, filename: str, original_caption: str, series_data: dict = None) -> str:
    """
    Format caption with all available variables
    
    Args:
        template: Caption template with variables like {filename}, {season}, etc.
        filename: Name of the file
        original_caption: Original caption of the file
        series_data: Dict containing series_name, language, quality from state_manager
    
    Returns:
        Formatted caption string
    """
    try:
        # Extract info from original caption
        extracted_info = extract_series_info(original_caption)
        
        # Use series_data if provided (from state_manager - more accurate)
        if series_data:
            series_name = series_data.get('series_name', extracted_info['seriesname'])
            language = series_data.get('language', extracted_info['language'])
            quality = series_data.get('quality', extracted_info['quality'])
        else:
            series_name = extracted_info['seriesname']
            language = extracted_info['language']
            quality = extracted_info['quality']
        
        # Prepare replacement dict
        replacements = {
            '{filename}': filename,
            '{filecaption}': original_caption,
            '{seriesname}': series_name,
            '{language}': language,
            '{quality}': quality,
            '{season}': extracted_info['season'],
            '{episode}': extracted_info['episode'],
            '{Season}': extracted_info['season'],  # Alias for {season}
            '{Episode}': extracted_info['episode']  # Alias for {episode}
        }
        
        # Replace all variables in template
        formatted_caption = template
        for var, value in replacements.items():
            formatted_caption = formatted_caption.replace(var, value)
        
        return formatted_caption
    
    except Exception as e:
        logger.error(f"Error formatting caption: {e}", exc_info=True)
        return template  # Return original template on error


# ============================================================================
# DATABASE FUNCTIONS FOR CAPTION TEMPLATE STORAGE
# ============================================================================

async def save_caption_template(user_id: int, template: str):
    """Save caption template for user"""
    return await db.save_caption_template(user_id, template)


async def get_caption_template(user_id: int) -> str:
    """Get caption template for user"""
    template = await db.get_caption_template(user_id)
    return template if template else DEFAULT_CAPTION


async def delete_caption_template(user_id: int):
    """Delete caption template for user"""
    return await db.delete_caption_template(user_id)


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

@Client.on_message(filters.command("filecaption") & filters.private)
async def set_caption_handler(client: Client, message: Message):
    """
    Handle /filecaption command to set custom caption template
    Usage: /filecaption <template>
    Example: /filecaption <code>{filename}</code>
    """
    user_id = message.from_user.id
    
    # Check if user is admin
    if user_id not in ADMINS:
        await message.reply_text(
            "❌ <b>Permission Denied</b>\n"
            "Only admins can set custom file captions.",
            quote=True
        )
        return
    
    # Check if template is provided
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        # Show current template
        current_template = await get_caption_template(user_id)
        
        await message.reply_text(
            f"<b>📝 Current File Caption Template:</b>\n\n"
            f"<code>{current_template}</code>\n\n"
            f"<b>Available Variables:</b>\n"
            f"• <code>{{filename}}</code> - File name\n"
            f"• <code>{{filecaption}}</code> - Original caption\n"
            f"• <code>{{seriesname}}</code> - Series name\n"
            f"• <code>{{language}}</code> - Language\n"
            f"• <code>{{quality}}</code> - Quality\n"
            f"• <code>{{season}}</code> - Season number\n"
            f"• <code>{{episode}}</code> - Episode number\n\n"
            f"<b>Usage:</b>\n"
            f"<code>/filecaption &lt;template&gt;</code>\n\n"
            f"<b>Example:</b>\n"
            f"<code>/filecaption &lt;b&gt;{{filename}}&lt;/b&gt;\n"
            f"🎬 {{seriesname}} | S{{season}}E{{episode}}\n"
            f"📺 {{quality}} | {{language}}</code>\n\n"
            f"<b>To reset:</b> <code>/delcaption</code>",
            quote=True
        )
        return
    
    # Get template
    template = command_parts[1].strip()
    
    # Save template
    success = await save_caption_template(user_id, template)
    
    if success:
        await message.reply_text(
            "✅ <b>File Caption Template Updated!</b>\n\n"
            f"<b>New Template:</b>\n"
            f"<code>{template}</code>\n\n"
            f"<b>Preview:</b>\n"
            f"{format_caption(template, 'Example.File.S01E05.720p.mkv', 'Breaking Bad S01E05 720p WEB-DL', {'series_name': 'Breaking Bad', 'language': 'English', 'quality': '720p'})}\n\n"
            f"This template will be used for all file uploads in batch creation.",
            quote=True
        )
    else:
        await message.reply_text(
            "❌ <b>Error</b>\n"
            "Failed to save caption template. Please try again.",
            quote=True
        )


@Client.on_message(filters.command("delcaption") & filters.private)
async def delete_caption_handler(client: Client, message: Message):
    """Handle /delcaption command to reset caption template"""
    user_id = message.from_user.id
    
    # Check if user is admin
    if user_id not in ADMINS:
        await message.reply_text(
            "❌ <b>Permission Denied</b>\n"
            "Only admins can manage file captions.",
            quote=True
        )
        return
    
    # Delete template
    success = await delete_caption_template(user_id)
    
    if success:
        await message.reply_text(
            "✅ <b>Caption Template Reset</b>\n\n"
            f"Default template restored: <code>{DEFAULT_CAPTION}</code>",
            quote=True
        )
    else:
        await message.reply_text(
            "❌ <b>Error</b>\n"
            "Failed to reset caption template.",
            quote=True
        )


@Client.on_message(filters.command("viewcaption") & filters.private)
async def view_caption_handler(client: Client, message: Message):
    """Handle /viewcaption command to view current template"""
    user_id = message.from_user.id
    
    # Check if user is admin
    if user_id not in ADMINS:
        await message.reply_text(
            "❌ <b>Permission Denied</b>\n"
            "Only admins can view file captions.",
            quote=True
        )
        return
    
    # Get current template
    current_template = await get_caption_template(user_id)
    
    await message.reply_text(
        f"<b>📝 Current File Caption Template:</b>\n\n"
        f"<code>{current_template}</code>\n\n"
        f"<b>Available Variables:</b>\n"
        f"• <code>{{filename}}</code> - File name\n"
        f"• <code>{{filecaption}}</code> - Original caption\n"
        f"• <code>{{seriesname}}</code> - Series name\n"
        f"• <code>{{language}}</code> - Language\n"
        f"• <code>{{quality}}</code> - Quality\n"
        f"• <code>{{season}}</code> - Season number\n"
        f"• <code>{{episode}}</code> - Episode number",
        quote=True
    )
