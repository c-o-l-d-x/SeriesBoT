from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from database.filters_mdb import del_all, del_allg
from database.connections_mdb import add_connection, active_connection, delete_connection
from info import ADMINS


# =================== CONNECTION COMMANDS ===================

@Client.on_message(filters.command('connect') & filters.private)
async def connect_handler(client, message):
    """Connect to a group for managing filters from PM"""
    userid = message.from_user.id
    
    if len(message.command) < 2:
        await message.reply_text(
            "<b>Usage:</b>\n"
            "/connect <group_id>\n\n"
            "Get group ID by using /id command in your group"
        )
        return
    
    try:
        group_id = int(message.command[1])
    except ValueError:
        await message.reply_text("❌ Invalid group ID! Please provide a valid numeric group ID.")
        return
    
    # Check if user is admin in the group
    try:
        chat = await client.get_chat(group_id)
        member = await client.get_chat_member(group_id, userid)
        
        if (
            member.status != enums.ChatMemberStatus.ADMINISTRATOR
            and member.status != enums.ChatMemberStatus.OWNER
            and userid not in ADMINS
        ):
            await message.reply_text("❌ You must be an admin in that group to connect!")
            return
        
        # Add connection
        await add_connection(userid, group_id)
        await message.reply_text(
            f"✅ Connected to <b>{chat.title}</b>\n\n"
            "Now you can manage filters for this group from here!",
            parse_mode=enums.ParseMode.HTML
        )
    except Exception as e:
        await message.reply_text(
            "❌ Failed to connect!\n"
            "Make sure:\n"
            "• I'm in that group\n"
            "• You're an admin there\n"
            "• The group ID is correct"
        )


@Client.on_message(filters.command('disconnect') & filters.private)
async def disconnect_handler(client, message):
    """Disconnect from current group connection"""
    userid = message.from_user.id
    
    group_id = await active_connection(str(userid))
    if group_id:
        await delete_connection(userid)
        await message.reply_text("✅ Disconnected from group!")
    else:
        await message.reply_text("❌ You're not connected to any group!")


@Client.on_message(filters.command('connections') & filters.private)
async def list_connections(client, message):
    """List current connection"""
    userid = message.from_user.id
    
    group_id = await active_connection(str(userid))
    if group_id:
        try:
            chat = await client.get_chat(int(group_id))
            await message.reply_text(
                f"<b>Current Connection:</b>\n"
                f"• {chat.title}\n"
                f"• ID: <code>{group_id}</code>",
                parse_mode=enums.ParseMode.HTML
            )
        except:
            await message.reply_text(
                f"<b>Current Connection:</b>\n"
                f"• ID: <code>{group_id}</code>\n"
                "(Unable to fetch group details)",
                parse_mode=enums.ParseMode.HTML
            )
    else:
        await message.reply_text("❌ You're not connected to any group!")


# =================== FILTER CALLBACKS ===================

@Client.on_callback_query(filters.regex('^delallconfirm$'))
async def delall_callback(client, callback_query: CallbackQuery):
    """Handle delete all filters confirmation"""
    userid = callback_query.from_user.id
    chat_type = callback_query.message.chat.type
    
    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                await callback_query.message.edit_text("Make sure I'm present in your group!!")
                return
        else:
            await callback_query.message.edit_text(
                "I'm not connected to any groups!\n"
                "Use /connect <group_id> to connect"
            )
            return
    else:
        grp_id = callback_query.message.chat.id
        title = callback_query.message.chat.title
    
    # Check if user is owner or admin
    st = await client.get_chat_member(grp_id, userid)
    if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
        await del_all(callback_query.message, grp_id, title)
    else:
        await callback_query.answer("Only group owner can do this!", show_alert=True)


@Client.on_callback_query(filters.regex('^delallcancel$'))
async def delall_cancel_callback(client, callback_query: CallbackQuery):
    """Handle cancel delete all filters"""
    userid = callback_query.from_user.id
    chat_type = callback_query.message.chat.type
    
    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
        else:
            await callback_query.message.edit_text("I'm not connected to any groups!")
            return
    else:
        grp_id = callback_query.message.chat.id
    
    st = await client.get_chat_member(grp_id, userid)
    if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
        await callback_query.message.edit_text("Deletion of all filters has been cancelled!")
    else:
        await callback_query.answer("Only group owner can do this!", show_alert=True)


# =================== GFILTER CALLBACKS ===================

@Client.on_callback_query(filters.regex('^gfiltersdeleteallconfirm$') & filters.user(ADMINS))
async def delallg_callback(client, callback_query: CallbackQuery):
    """Handle delete all global filters confirmation (admin only)"""
    await del_allg(callback_query.message, 'gfilters')


@Client.on_callback_query(filters.regex('^gfiltersdeleteallcancel$') & filters.user(ADMINS))
async def delallg_cancel_callback(client, callback_query: CallbackQuery):
    """Handle cancel delete all global filters (admin only)"""
    await callback_query.message.edit_text("Deletion of all gfilters has been cancelled!")
