import base64
import re
from pyrogram.types import Message
from pyrogram import Client

async def encode(string):
    """Encode string to base64"""
    string_bytes = string.encode("ascii")
    base64_bytes = base64.urlsafe_b64encode(string_bytes)
    base64_string = base64_bytes.decode("ascii").strip("=")
    return base64_string

async def decode(base64_string):
    """Decode base64 string"""
    base64_string = base64_string.strip("=")
    base64_bytes = (base64_string + "=" * (-len(base64_string) % 4)).encode("ascii")
    string_bytes = base64.urlsafe_b64decode(base64_bytes) 
    string = string_bytes.decode("ascii")
    return string

async def get_message_id(client: Client, message: Message):
    """
    Get message ID from forwarded message or channel link
    Returns the message ID if valid, None otherwise
    """
    if message.forward_from_chat:
        # This is a forwarded message
        if message.forward_from_chat.id == client.main_db_channel.id:
            return message.forward_from_message_id
        else:
            return None
    
    elif message.text:
        # This might be a channel link
        pattern = r"https://t\.me/(?:c/)?(.+)/(\d+)"
        match = re.match(pattern, message.text)
        
        if not match:
            return None
        
        channel_id = match.group(1)
        msg_id = int(match.group(2))
        
        # Check if it's from the DB channel
        # Handle both public (@username) and private (-100xxx) channels
        if channel_id.isdigit():
            # Private channel: -100 + channel_id
            if int(f"-100{channel_id}") == client.main_db_channel.id:
                return msg_id
        else:
            # Public channel: check username
            try:
                db_channel = await client.get_chat(client.main_db_channel.id)
                if hasattr(db_channel, 'username') and db_channel.username == channel_id:
                    return msg_id
            except:
                pass
        
        return None
    
    return None
