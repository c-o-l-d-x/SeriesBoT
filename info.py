import os
from os import environ

# Bot Information
API_ID = int(environ.get("API_ID", "20400973"))
API_HASH = environ.get("API_HASH", "047838cb76d54bc445e155a7cab44664")
BOT_TOKEN = environ.get("BOT_TOKEN", "8039661078:AAF7Y7FRGJe9_rZDJvC0RjWZmHDKUpOYkFw")

# Database Information
DATABASE_URI = environ.get("DATABASE_URI", "mongodb+srv://amalabraham989:seriesfactory@sfactory.a7gq1.mongodb.net/?retryWrites=true&w=majority&appName=sfactory")
DATABASE_NAME = environ.get("DATABASE_NAME", "sfactory")

# API Keys for Metadata
TMDB_API_KEY = environ.get("TMDB_API_KEY", "8c18c4bde8c3c8e1c1c6236d29af7dd7")
OMDB_API_KEY = environ.get("OMDB_API_KEY", "3939abc8")
IMGBB_API_KEY = environ.get("IMGBB_API_KEY", "c802c6d010120404a4e18a526873fdaa")

# Admin and Channel Information
ADMINS = [int(admin) if admin.strip().isdigit() else admin for admin in environ.get('ADMINS', '5677517133 5329179170').split()]

# Main DB Channel for Batch Storage
# This is where all batch messages will be stored
main_db_str = environ.get('MAIN_DB_CHANNEL', '-1003560881754')
if main_db_str.startswith('@'):
    MAIN_DB_CHANNEL = main_db_str  # Username format
else:
    MAIN_DB_CHANNEL = int(main_db_str) if main_db_str.lstrip('-').isdigit() and main_db_str != '0' else None

# Update Channel for Series Updates
# This is where update messages will be sent when series are published/updated
update_channel_str = environ.get('UPDATE_CHANNEL', '-1003749164129')
if update_channel_str.startswith('@'):
    UPDATE_CHANNEL = update_channel_str  # Username format
else:
    UPDATE_CHANNEL = int(update_channel_str) if update_channel_str.lstrip('-').isdigit() and update_channel_str != '0' else None
  
# Optional Settings
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1002361556192")) if environ.get("LOG_CHANNEL", "0").lstrip('-').isdigit() else None

# Custom File Caption for Batch Messages (Supports HTML)
# Available variables: {file_name}, {file_caption}
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", "<code>{file_name}</code>\n@SeriesFactory")

PROTECT_CONTENT = environ.get("PROTECT_CONTENT", "False") == "True"
AUTO_DELETE_TIME = int(environ.get("AUTO_DELETE_TIME", "0"))

# Variables for old plugins (to prevent import errors)
AUTH_CHANNEL = environ.get("AUTH_CHANNEL", "0")
LONG_IMDB_DESCRIPTION = environ.get("LONG_IMDB_DESCRIPTION", "False") == "True"
MAX_LIST_ELM = int(environ.get("MAX_LIST_ELM", "10"))
REQ_CHANNEL_ONE = int(environ.get("REQ_CHANNEL_ONE", "0")) if environ.get("REQ_CHANNEL_ONE", "0").lstrip('-').isdigit() else 0
REQ_CHANNEL_TWO = int(environ.get("REQ_CHANNEL_TWO", "0")) if environ.get("REQ_CHANNEL_TWO", "0").lstrip('-').isdigit() else 0
RAW_DB_CHANNEL = int(environ.get("RAW_DB_CHANNEL", "0")) if environ.get("RAW_DB_CHANNEL", "0").lstrip('-').isdigit() else 0

# Additional variables (if needed by old plugins)
SUPPORT_CHAT = environ.get("SUPPORT_CHAT", "")
PICS = environ.get("PICS", "https://telegra.ph/file/d440b16d7c5b8e52e15de.jpg").split()
