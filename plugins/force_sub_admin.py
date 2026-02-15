# -*- coding: utf-8 -*-
"""
Force Subscribe Admin Commands
Commands for admins to manage force subscribe settings
"""
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from database.force_sub_db import force_sub_db
from plugins.force_sub_handler import clear_invite_link_cache
from info import ADMINS
import logging

logger = logging.getLogger(__name__)


@Client.on_message(filters.command("fsub") & filters.private & filters.user(ADMINS))
async def force_sub_settings(client: Client, message: Message):
    """Show force subscribe settings and status"""
    try:
        settings = await force_sub_db.get_settings()
        
        enabled = settings.get('enabled', False)
        mode = settings.get('mode', 'request')
        channel_id = settings.get('channel_id')
        user_count = await force_sub_db.get_all_users_count()
        
        status_emoji = "✅" if enabled else "❌"
        mode_text = "Request to Join" if mode == "request" else "Instant Join"
        
        text = f"""
<b>⚙️ Force Subscribe Settings</b>

<b>Status:</b> <code>{status_emoji} {'Enabled' if enabled else 'Disabled'}</code>
<b>Mode:</b> <code>{mode_text}</code>
<b>Channel ID:</b> <code>{channel_id if channel_id else 'Not Set'}</code>
<b>Authorized Users:</b> <code>{user_count}</code>

<b>Commands:</b>
• <code>/fsub_enable</code> <mode>
<i>Enable force sub</i>
<i>Mode:</i> <code>request</code> or <code>normal</code>
<i>Example:</i> <code>/fsub_enable request</code>

• <code>/fsub_disable</code>
<i>Disable force sub</i>

• <code>/fsub_channel</code> <channel_id>
<i>Set channel</i>
<i>Example:</i> <code>/fsub_channel -1001234567890</code>

• <code>/fsub_message</code> 
<i>Set custom message (reply to message)</i>

• <code>/fsub_stats</code>
<i>View authorized users stats</i>

• <code>/fsub_clear</code>
<i>Clear all authorized users</i>

{'<b>Request Mode:</b> Users Need To Send Join Request' if mode == 'request' else '<b>Normal Mode:</b> Users Need To Join Channel'}
"""
        
        await message.reply_text(text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error showing force sub settings: {e}", exc_info=True)
        await message.reply_text("❌ Error retrieving settings!")


@Client.on_message(filters.command("fsub_enable") & filters.private & filters.user(ADMINS))
async def enable_force_sub(client: Client, message: Message):
    """Enable force subscribe with specified mode"""
    try:
        # Get mode from command
        if len(message.command) < 2:
            await message.reply_text(
                "❌ Please specify mode!\n\n"
                "<b>Usage:</b> <code>/fsub_enable <mode></code>\n"
                "<b>Modes:</b>\n"
                "• <code>request</code> - Users send join request (auto-approved)\n"
                "• <code>normal</code> - Users must actually join\n\n"
                "<b>Example:</b> <code>/fsub_enable request</code>"
            )
            return
        
        mode = message.command[1].lower()
        
        if mode not in ['request', 'normal']:
            await message.reply_text(
                "❌ Invalid mode!\n\n"
                "Valid modes: <code>request</code> or <code>normal</code>"
            )
            return
        
        # Check if channel is set
        settings = await force_sub_db.get_settings()
        if not settings.get('channel_id'):
            await message.reply_text(
                "⚠️ Please set a channel first!\n\n"
                "Use: <code>/fsub_channel <channel_id></code>"
            )
            return
        
        # Enable force sub
        await force_sub_db.enable_force_sub(mode=mode)
        
        # Clear invite link cache
        clear_invite_link_cache()
        
        mode_text = "Request to Join" if mode == "request" else "Instant Join"
        
        await message.reply_text(
            f"✅ Force Subscribe <b>Enabled</b>!\n\n"
            f"<b>Mode:</b> {mode_text}\n"
            f"<b>Channel:</b> <code>{settings.get('channel_id')}</code>"
        )
        
    except Exception as e:
        logger.error(f"Error enabling force sub: {e}", exc_info=True)
        await message.reply_text("❌ Error enabling force subscribe!")


@Client.on_message(filters.command("fsub_disable") & filters.private & filters.user(ADMINS))
async def disable_force_sub(client: Client, message: Message):
    """Disable force subscribe"""
    try:
        await force_sub_db.disable_force_sub()
        
        # Clear invite link cache
        clear_invite_link_cache()
        
        await message.reply_text("✅ Force Subscribe <b>Disabled</b>!")
        
    except Exception as e:
        logger.error(f"Error disabling force sub: {e}", exc_info=True)
        await message.reply_text("❌ Error disabling force subscribe!")


@Client.on_message(filters.command("fsub_channel") & filters.private & filters.user(ADMINS))
async def set_force_sub_channel(client: Client, message: Message):
    """Set force subscribe channel"""
    try:
        if len(message.command) < 2:
            await message.reply_text(
                "❌ Please provide channel ID!\n\n"
                "<b>Usage:</b> <code>/fsub_channel <channel_id></code>\n"
                "<b>Example:</b> <code>/fsub_channel -1001234567890</code>\n\n"
                "<b>Note:</b> Make sure the bot is admin in the channel with invite link permission!"
            )
            return
        
        channel_input = message.command[1]
        
        # Try to parse as integer
        try:
            channel_id = int(channel_input)
        except ValueError:
            await message.reply_text("❌ Invalid channel ID! Must be a number.")
            return
        
        # Try to get channel info to verify
        try:
            chat = await client.get_chat(channel_id)
            channel_username = chat.username
            
            # Check if bot is admin
            bot_member = await client.get_chat_member(channel_id, client.me.id)
            if not bot_member.privileges or not bot_member.privileges.can_invite_users:
                await message.reply_text(
                    "⚠️ Warning: Bot might not have permission to create invite links!\n\n"
                    "Make sure the bot is admin with 'Invite Users' permission."
                )
            
        except Exception as e:
            await message.reply_text(
                f"⚠️ Could not verify channel: {e}\n\n"
                "Make sure:\n"
                "1. Channel ID is correct\n"
                "2. Bot is added to the channel\n"
                "3. Bot is admin with invite permission\n\n"
                "Proceeding anyway..."
            )
            channel_username = None
        
        # Set channel
        await force_sub_db.set_channel(channel_id, channel_username)
        
        # Clear invite link cache
        clear_invite_link_cache()
        
        await message.reply_text(
            f"✅ Force Subscribe channel set!\n\n"
            f"<b>Channel ID:</b> <code>{channel_id}</code>\n"
            f"<b>Username:</b> @{channel_username if channel_username else 'Private Channel'}"
        )
        
    except Exception as e:
        logger.error(f"Error setting force sub channel: {e}", exc_info=True)
        await message.reply_text("❌ Error setting channel!")


@Client.on_message(filters.command("fsub_message") & filters.private & filters.user(ADMINS))
async def set_force_sub_message(client: Client, message: Message):
    """Set custom force subscribe message"""
    try:
        if not message.reply_to_message:
            await message.reply_text(
                "❌ Please reply to a message containing your custom force sub message!\n\n"
                "<b>Usage:</b> Reply to your custom message with <code>/fsub_message</code>\n\n"
                "<b>Tip:</b> You can use formatting (bold, italic, etc.)"
            )
            return
        
        custom_message = message.reply_to_message.text or message.reply_to_message.caption
        
        if not custom_message:
            await message.reply_text("❌ Message is empty!")
            return
        
        # Set custom message
        await force_sub_db.set_force_message(custom_message)
        
        await message.reply_text(
            "✅ Custom force subscribe message set!\n\n"
            "<b>Preview:</b>\n" + custom_message
        )
        
    except Exception as e:
        logger.error(f"Error setting force sub message: {e}", exc_info=True)
        await message.reply_text("❌ Error setting message!")


@Client.on_message(filters.command("fsub_stats") & filters.private & filters.user(ADMINS))
async def force_sub_stats(client: Client, message: Message):
    """Show force subscribe statistics"""
    try:
        settings = await force_sub_db.get_settings()
        total_users = await force_sub_db.get_all_users_count()
        
        enabled = settings.get('enabled', False)
        mode = settings.get('mode', 'request')
        channel_id = settings.get('channel_id')
        
        status_emoji = "✅" if enabled else "❌"
        mode_text = "Request to Join" if mode == "request" else "Instant Join"
        
        text = f"""
<b>📊 Force Subscribe Statistics</b>

<b>Status:</b> {status_emoji} {'Enabled' if enabled else 'Disabled'}
<b>Mode:</b> {mode_text}
<b>Channel:</b> <code>{channel_id if channel_id else 'Not Set'}</code>

<b>Total Authorized Users:</b> {total_users}

<b>Note:</b> Authorized users can access content without joining again.
"""
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Clear All Users", callback_data="fsub_clear_confirm")]
        ])
        
        await message.reply_text(text, reply_markup=buttons)
        
    except Exception as e:
        logger.error(f"Error showing force sub stats: {e}", exc_info=True)
        await message.reply_text("❌ Error retrieving statistics!")


@Client.on_message(filters.command("fsub_clear") & filters.private & filters.user(ADMINS))
async def clear_force_sub_users(client: Client, message: Message):
    """Clear all authorized users"""
    try:
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Clear All", callback_data="fsub_clear_yes"),
                InlineKeyboardButton("❌ Cancel", callback_data="fsub_clear_no")
            ]
        ])
        
        await message.reply_text(
            "⚠️ <b>Are you sure?</b>\n\n"
            "This will remove ALL authorized users from the database.\n"
            "They will need to join/request again to access content.",
            reply_markup=buttons
        )
        
    except Exception as e:
        logger.error(f"Error clearing force sub users: {e}", exc_info=True)
        await message.reply_text("❌ Error!")


# Callback handlers for clear confirmation
@Client.on_callback_query(filters.regex("^fsub_clear"))
async def handle_clear_callback(client: Client, callback_query):
    """Handle clear confirmation callbacks"""
    try:
        data = callback_query.data
        
        if data == "fsub_clear_yes":
            deleted_count = await force_sub_db.delete_all_users()
            await callback_query.message.edit_text(
                f"✅ Successfully cleared <b>{deleted_count}</b> authorized users!"
            )
        
        elif data == "fsub_clear_no":
            await callback_query.message.edit_text("❌ Cancelled!")
        
        elif data == "fsub_clear_confirm":
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes, Clear All", callback_data="fsub_clear_yes"),
                    InlineKeyboardButton("❌ Cancel", callback_data="fsub_clear_no")
                ]
            ])
            
            await callback_query.message.edit_text(
                "⚠️ <b>Are you sure?</b>\n\n"
                "This will remove ALL authorized users from the database.\n"
                "They will need to join/request again to access content.",
                reply_markup=buttons
            )
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Error handling clear callback: {e}", exc_info=True)
        await callback_query.answer("❌ Error!", show_alert=True)
