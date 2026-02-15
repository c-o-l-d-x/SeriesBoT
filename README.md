# 📺 Series Bot - Clean & Optimized

A clean, optimized Telegram bot for distributing TV series using **batch forwarding method only**. Files are NOT uploaded to database - only message IDs are stored.

## ✨ Key Features

### 🎯 Core Functionality
- **Batch Forwarding Only**: No file uploads, only message ID storage
- **No Forward Tags**: Users receive files without "Forwarded from" tags
- **MongoDB**: Stores only series structure and message IDs (not files)
- **Multi-level Organization**: Series → Language → Season → Quality
- **Publish Control**: Content visible only after admin publishes

### 📋 Admin Workflow

1. **Create Series**: `/newseries Dark`
2. **Add Language**: Click buttons or type custom name
3. **Add Season**: Click buttons or type custom name
4. **Add Quality**: Click buttons or type custom name
5. **Forward First Message**: Forward from DB channel WITH tag
6. **Forward Last Message**: Forward from DB channel WITH tag
7. **Publish**: Click publish button
8. **Done!** Users can now access

### 👥 User Workflow

1. Start bot → See series list
2. Select series → See languages
3. Select language → See seasons
4. Select season → See qualities
5. Select quality → Receive all files **without forward tags**

## 🚀 Installation

### Prerequisites
- Python 3.8+
- MongoDB database
- Telegram Bot Token
- Private DB Channel(s)

### Setup

1. **Clone/Download**
   ```bash
   cd SeriesBot-Clean
   ```

2. **Install Dependencies**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Configure**
   
   Rename `sample_info.py` to `info.py` and fill in your details:
   ```python
   API_ID = "12345678"
   API_HASH = "abcdef1234567890"
   BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
   DATABASE_URI = "mongodb+srv://user:pass@cluster.mongodb.net/"
   ADMINS = "123456789 987654321"
   DB_CHANNEL = "-1001234567890"
   ```

4. **Run**
   ```bash
   python3 bot.py
   ```

## 📖 Detailed Guide

### Getting Your Credentials

**API_ID & API_HASH**:
1. Go to https://my.telegram.org
2. Log in with your phone number
3. Go to "API Development Tools"
4. Create an app
5. Copy API_ID and API_HASH

**BOT_TOKEN**:
1. Message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Follow instructions
4. Copy the token

**DATABASE_URI**:
1. Go to https://mongodb.com
2. Create free cluster
3. Get connection string
4. Replace `<password>` with your password

**DB_CHANNEL**:
1. Create private channel
2. Add bot as admin with all permissions
3. Forward any message from channel to [@userinfobot](https://t.me/userinfobot)
4. Copy channel ID (negative number)

**ADMINS**:
1. Message [@userinfobot](https://t.me/userinfobot)
2. Copy your user ID

### First Series Setup

1. **Add Series**
   ```
   /newseries Dark
   ```

2. **Add Language**
   - Click "➕ Language"
   - Click "German" (or type custom name)

3. **Add Season**
   - Click "➕ Seasons"
   - Click "Season 1" (or type custom name)

4. **Add Quality**
   - Click "➕ Quality"
   - Click "720p" (or type custom name)

5. **Upload Files to DB Channel**
   - Upload all episodes to your DB channel
   - Note the message IDs (e.g., 100-109)

6. **Set Batch**
   - Bot asks: "Forward first file (with tag)"
   - Forward message 100 from DB channel **with forward tag enabled**
   - Bot asks: "Forward last file (with tag)"
   - Forward message 109 from DB channel **with forward tag enabled**
   - Bot saves: "Batch saved! 10 messages"

7. **Publish**
   - Click "✅ Publish"
   - Done!

## 🔑 Important Notes

### Forward Tags
- **When setting batch**: Keep forward tags **ENABLED**
- **When users download**: Bot automatically removes tags using `copy_message`

### Batch Range
- Bot sends ALL messages between first and last ID
- Example: first=100, last=109 → sends 100,101,102...109
- Make sure no unwanted messages in between!

### File Types Supported
- Videos (.mp4, .mkv, etc.)
- Documents (.zip, .pdf, etc.)
- Photos
- Audio files
- Text messages
- Any combination in same batch

### Database Storage
- **Bot DOES NOT store files in MongoDB**
- Only stores:
  - Series structure (name, metadata)
  - Message IDs (first, last, channel ID)
  - Publish status
- Files stay in your DB channel
- Very efficient and lightweight!

## 📁 Project Structure

```
SeriesBot-Clean/
├── bot.py                  # Main bot file
├── info.py                 # Configuration (create from sample)
├── sample_info.py          # Configuration template
├── requirements.txt        # Dependencies
├── README.md              # This file
├── database/
│   └── series_db.py       # MongoDB operations (IDs only)
└── plugins/
    └── series.py          # Series management plugin
```

## 🎮 Commands

### Admin Commands
- `/newseries <name>` - Add new series
- `/start` - View admin panel / Browse series

### User Commands
- `/start` - Browse available series

## 💾 Database Structure

```json
{
  "_id": "dark",
  "title": "Dark",
  "year": "2017-2020",
  "genre": "Crime, Drama, Mystery",
  "rating": "8.7",
  "poster_id": null,
  "languages": {
    "german": {
      "name": "German",
      "poster_id": null,
      "seasons": {
        "season_1": {
          "name": "Season 1",
          "poster_id": null,
          "qualities": {
            "720p": {
              "name": "720p",
              "first_msg_id": 100,
              "last_msg_id": 109,
              "db_channel_id": -1001234567890,
              "published": true
            }
          }
        }
      }
    }
  }
}
```

## ❓ Troubleshooting

### Bot doesn't respond
- Check bot token is correct
- Ensure bot is running
- Check API_ID and API_HASH

### Can't forward messages
- Bot must be admin in DB channel
- Check DB_CHANNEL ID is correct (negative)
- Enable "Show Sender's Name" when forwarding

### Users see forward tags
- Report this as a bug (shouldn't happen)
- Bot uses `copy_message` which removes tags

### Batch not working
- Check first_msg_id < last_msg_id
- Verify bot has access to DB channel
- Make sure quality is published

### Database connection error
- Check DATABASE_URI is correct
- Ensure MongoDB cluster is running
- Verify network connectivity

## 🔒 Security

- Never share your bot token
- Keep info.py private
- Don't commit credentials to git
- Use strong MongoDB password
- Keep DB channel private

## 📝 Changelog

### v1.0.0 (Clean Version)
- ✅ Batch forwarding method only
- ✅ No file uploads to database
- ✅ Store only message IDs
- ✅ Send without forward tags
- ✅ Clean, optimized code
- ✅ All media types supported
- ✅ Publish control
- ✅ User-friendly interface

## 🤝 Support

Having issues?
1. Check this README carefully
2. Verify all credentials are correct
3. Check bot logs for errors
4. Ensure all requirements are installed

---

**Made for efficient series distribution** 🎬

## 🆕 New Features (v2.0)

### Enhanced Commands
- **`/editseries`** - Edit existing series without recreating
- **`/deleteseries`** - Delete specific series with confirmation
- **`/viewseries`** - View detailed series information with batch counts
- **`/viewall`** - List all series with count
- **`/deleteall`** - Delete all series (with double confirmation)
- **`/recent`** - View 10 most recent series (available to all users)

### Features
- ✅ Edit existing series - add more content anytime
- ✅ View series details - see all languages, seasons, qualities
- ✅ Batch message counts - see how many files in each quality
- ✅ Recent series list - users can discover new content
- ✅ Confirmation dialogs - prevent accidental deletions
- ✅ Language management - add, edit, delete languages
- ✅ Season management - add, edit, delete seasons

### Command Quick Reference
See [COMMANDS.md](COMMANDS.md) for detailed documentation with examples.

---

