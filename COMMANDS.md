# 📋 Bot Commands Reference

## 🔐 Admin Commands

### Series Management

**`/newseries <series_name>`**
- Add a new series to the bot
- Example: `/newseries Dark`
- Opens interactive menu to add languages, seasons, and qualities

**`/editseries <series_name>`**
- Edit an existing series
- Add more languages, seasons, or qualities
- View current structure
- Example: `/editseries Dark`

**`/deleteseries <series_name>`**
- Delete a specific series
- Removes all associated data (languages, seasons, qualities, batches)
- Requires confirmation
- Example: `/deleteseries Dark`

**`/viewseries <series_name>`**
- View detailed information about a series
- Shows:
  - All languages
  - All seasons
  - All qualities
  - Batch message counts
  - Message ID ranges
  - Publish status
- Example: `/viewseries Dark`

**`/viewall`**
- View all series in the database
- Shows:
  - Total series count
  - List of all series names
  - Language count for each series

**`/deleteall`**
- Delete ALL series from the database
- **DANGER**: This action cannot be undone
- Requires double confirmation
- Use with extreme caution

**`/start`**
- Admin panel (for admins)
- Browse series (for users)

---

## 👥 User Commands

**`/start`**
- Browse available series
- Navigate through languages, seasons, and qualities
- Download files

**`/recent`**
- View the 10 most recently added series
- Quick access to new content
- Shows list with browse button

---

## 📖 Usage Examples

### Adding a Complete Series

```
Step 1: Create series
/newseries Dark

Step 2: Click "➕ Language" → Select "German"

Step 3: Click "➕ Seasons" → Select "Season 1"

Step 4: Click "➕ Quality" → Select "720p"

Step 5: Upload files to DB channel (IDs 100-109)

Step 6: Forward message 100 to bot (with tag)

Step 7: Forward message 109 to bot (with tag)

Step 8: Click "✅ Publish"

Done! Series is live.
```

### Editing Existing Series

```
/editseries Dark

Options:
- ➕ Add Language (add Spanish, French, etc.)
- 📋 Manage Existing (edit languages/seasons)
- 🗑 Delete Series
```

### Viewing Series Details

```
/viewseries Dark

Output:
📺 Dark
━━━━━━━━━━━━━━━━

📅 Year: 2017-2020
🎭 Genre: Crime, Drama, Mystery
⭐ Rating: 8.7

━━━━━━━━━━━━━━━━

🌐 German
   📺 Season 1
      🎬 720p - ✅ Published
         📊 10 messages (ID: 100-110)
      🎬 1080p - ⏳ Not Published
```

### Managing Content

```
# View all series
/viewall

Output:
📊 Total Series: 5
━━━━━━━━━━━━━━━━

1. Dark (2 langs)
2. Stranger Things (3 langs)
3. Breaking Bad (1 lang)
4. Game of Thrones (2 langs)
5. The Witcher (1 lang)
```

### Deleting Content

```
# Delete specific series
/deleteseries Dark

# Delete all series (careful!)
/deleteall
```

---

## 🔔 Important Notes

### For Admins:
- All admin commands work only in private chat
- Batch files must be forwarded WITH forward tags enabled
- Always publish after setting batch range
- Users can only see published qualities

### For Users:
- `/recent` command shows latest additions
- Files are sent without forward tags
- All media types are supported (video, documents, images, text)

---

## 💡 Tips & Tricks

### Batch Organization
- Upload files in episode order to DB channel
- Message IDs will be sequential
- Makes batch setup easier

### Multiple Qualities
- Add different qualities separately (480p, 720p, 1080p)
- Users can choose their preferred quality
- Each quality has its own batch range

### Content Updates
- Use `/editseries` to add more content
- No need to recreate entire series
- Can add languages/seasons anytime

### Quick View
- Use `/recent` for quick access to new series
- Users love discovering new content
- Updates automatically

---

## ⚠️ Important Warnings

### Delete Commands
- `/deleteseries` - Deletes one series permanently
- `/deleteall` - Deletes EVERYTHING permanently
- Both require confirmation
- No way to undo

### Best Practices
- Always use `/viewseries` before deleting
- Use `/viewall` to see what you have
- Keep backups of important series data
- Test with one series before bulk upload

---

## 🆘 Command Troubleshooting

**Command not working?**
- Check spelling (case-sensitive names)
- Use quotes for series with spaces: `/newseries "My Series"`
- Or use underscores: `/newseries My_Series`

**Can't find series?**
- Use `/viewall` to see all series
- Check series name spelling
- Series names are case-insensitive

**Accidental deletion?**
- No recovery possible
- Always confirm carefully
- Keep original files in DB channel

---

Made with ❤️ for efficient series management
