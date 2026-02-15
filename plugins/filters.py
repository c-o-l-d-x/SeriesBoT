import io
from pyrogram import filters, Client, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.filters_mdb import (
    add_filter,
    get_filters,
    delete_filter,
    count_filters,
    add_gfilter,
    get_gfilters,
    delete_gfilter,
    count_gfilters
)
from database.connections_mdb import active_connection
from utils import get_file_id, parser, gfilterparser, split_quotes
from info import ADMINS
from permission_helper import is_auth_user_or_admin  # NEW: For auth user support
from auth_manager import auth_manager  # NEW: For auth user support


# Custom filter for auth users + admins (dynamic check)
async def auth_filter_func(_, __, message):
    """Custom filter function that dynamically checks if user is admin or auth user"""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return False
    # Check if user is admin or auth user (dynamically checked each time)
    return is_auth_user_or_admin(user_id)

# Create the custom filter
auth_filter = filters.create(auth_filter_func)


# ========== FILTER COMMANDS ==========

@Client.on_message(filters.command(['filter', 'add']) & filters.incoming & auth_filter)
async def addfilter(client, message):
    """Add a new filter to the group"""
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    
    chat_type = message.chat.type
    args = message.text.html.split(None, 1)

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title

    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status != enums.ChatMemberStatus.ADMINISTRATOR
        and st.status != enums.ChatMemberStatus.OWNER
        and str(userid) not in ADMINS
    ):
        return

    if len(args) < 2:
        await message.reply_text("Command Incomplete :(", quote=True)
        return

    extracted = split_quotes(args[1])
    text = extracted[0].lower()

    if not message.reply_to_message and len(extracted) < 2:
        await message.reply_text("Add some content to save your filter!", quote=True)
        return

    if (len(extracted) >= 2) and not message.reply_to_message:
        reply_text, btn, alert = parser(extracted[1], text)
        fileid = None
        if not reply_text:
            await message.reply_text("You cannot have buttons alone, give some text to go with it!", quote=True)
            return

    elif message.reply_to_message and message.reply_to_message.reply_markup:
        try:
            rm = message.reply_to_message.reply_markup
            btn = rm.inline_keyboard
            msg = get_file_id(message.reply_to_message)
            if msg:
                fileid = msg.file_id
                reply_text = message.reply_to_message.caption.html
            else:
                reply_text = message.reply_to_message.text.html
                fileid = None
            alert = None
        except:
            reply_text = ""
            btn = "[]"
            fileid = None
            alert = None

    elif message.reply_to_message and message.reply_to_message.media:
        try:
            msg = get_file_id(message.reply_to_message)
            fileid = msg.file_id if msg else None
            reply_text, btn, alert = parser(extracted[1], text) if message.reply_to_message.sticker else parser(message.reply_to_message.caption.html, text)
        except:
            reply_text = ""
            btn = "[]"
            alert = None
    elif message.reply_to_message and message.reply_to_message.text:
        try:
            fileid = None
            reply_text, btn, alert = parser(message.reply_to_message.text.html, text)
        except:
            reply_text = ""
            btn = "[]"
            alert = None
    else:
        return

    await add_filter(grp_id, text, reply_text, btn, fileid, alert)

    await message.reply_text(
        f"Filter for <code>{text}</code> added in <b>{title}</b>",
        quote=True,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_message(filters.command(['viewfilters', 'filters']) & filters.incoming & auth_filter)
async def get_all(client, message):
    """View all filters in the group"""
    chat_type = message.chat.type
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    
    if chat_type == enums.ChatType.PRIVATE:
        userid = message.from_user.id
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title

    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status != enums.ChatMemberStatus.ADMINISTRATOR
        and st.status != enums.ChatMemberStatus.OWNER
        and str(userid) not in ADMINS
    ):
        return

    texts = await get_filters(grp_id)
    count = await count_filters(grp_id)
    if count:
        filterlist = f"Total number of filters in <b>{title}</b> : {count}\n\n"

        for text in texts:
            keywords = " ×  <code>{}</code>\n".format(text)
            filterlist += keywords

        if len(filterlist) > 4096:
            with io.BytesIO(str.encode(filterlist.replace("<code>", ""))) as keyword_file:
                keyword_file.name = "keywords.txt"
                await message.reply_document(
                    document=keyword_file,
                    quote=True
                )
            return
    else:
        filterlist = f"There are no active filters in <b>{title}</b>"

    await message.reply_text(
        text=filterlist,
        quote=True,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_message(filters.command('del') & filters.incoming & auth_filter)
async def deletefilter(client, message):
    """Delete a specific filter"""
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title

    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status != enums.ChatMemberStatus.ADMINISTRATOR
        and st.status != enums.ChatMemberStatus.OWNER
        and str(userid) not in ADMINS
    ):
        return

    try:
        cmd, text = message.text.split(" ", 1)
    except:
        await message.reply_text(
            "<i>Mention the filtername which you wanna delete!</i>\n\n"
            "<code>/del filtername</code>\n\n"
            "Use /viewfilters to view all available filters",
            quote=True
        )
        return

    query = text.lower()
    await delete_filter(message, query, grp_id)


@Client.on_message(filters.command('delall') & filters.incoming & filters.user(ADMINS))
async def delallconfirm(client, message):
    """Delete all filters confirmation"""
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return

    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title

    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
        await message.reply_text(
            f"This will delete all filters from '{title}'.\nDo you want to continue??",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(text="YES", callback_data="delallconfirm")],
                [InlineKeyboardButton(text="CANCEL", callback_data="delallcancel")]
            ]),
            quote=True
        )


# ========== GFILTER COMMANDS ==========

@Client.on_message(filters.command(['gfilter', 'addg']) & filters.incoming & auth_filter)
async def addgfilter(client, message):
    """Add a new global filter (admin only)"""
    args = message.text.html.split(None, 1)

    if len(args) < 2:
        await message.reply_text("Command Incomplete :(", quote=True)
        return

    extracted = split_quotes(args[1])
    text = extracted[0].lower()

    if not message.reply_to_message and len(extracted) < 2:
        await message.reply_text("Add some content to save your filter!", quote=True)
        return

    if (len(extracted) >= 2) and not message.reply_to_message:
        reply_text, btn, alert = gfilterparser(extracted[1], text)
        fileid = None
        if not reply_text:
            await message.reply_text("You cannot have buttons alone, give some text to go with it!", quote=True)
            return

    elif message.reply_to_message and message.reply_to_message.reply_markup:
        try:
            rm = message.reply_to_message.reply_markup
            btn = rm.inline_keyboard
            msg = get_file_id(message.reply_to_message)
            if msg:
                fileid = msg.file_id
                reply_text = message.reply_to_message.caption.html
            else:
                reply_text = message.reply_to_message.text.html
                fileid = None
            alert = None
        except:
            reply_text = ""
            btn = "[]"
            fileid = None
            alert = None

    elif message.reply_to_message and message.reply_to_message.media:
        try:
            msg = get_file_id(message.reply_to_message)
            fileid = msg.file_id if msg else None
            reply_text, btn, alert = gfilterparser(extracted[1], text) if message.reply_to_message.sticker else gfilterparser(message.reply_to_message.caption.html, text)
        except:
            reply_text = ""
            btn = "[]"
            alert = None
    elif message.reply_to_message and message.reply_to_message.text:
        try:
            fileid = None
            reply_text, btn, alert = gfilterparser(message.reply_to_message.text.html, text)
        except:
            reply_text = ""
            btn = "[]"
            alert = None
    else:
        return

    await add_gfilter('gfilters', text, reply_text, btn, fileid, alert)

    await message.reply_text(
        f"GFilter for <code>{text}</code> added",
        quote=True,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_message(filters.command(['viewgfilters', 'gfilters']) & filters.incoming & auth_filter)
async def get_all_gfilters(client, message):
    """View all global filters (admin only)"""
    texts = await get_gfilters('gfilters')
    count = await count_gfilters('gfilters')
    if count:
        gfilterlist = f"Total number of gfilters : {count}\n\n"

        for text in texts:
            keywords = " ×  </code>{}<code>\n".format(text)
            gfilterlist += keywords

        if len(gfilterlist) > 4096:
            with io.BytesIO(str.encode(gfilterlist.replace("</code>", ""))) as keyword_file:
                keyword_file.name = "keywords.txt"
                await message.reply_document(
                    document=keyword_file,
                    quote=True
                )
            return
    else:
        gfilterlist = f"There are no active gfilters."

    await message.reply_text(
        text=gfilterlist,
        quote=True,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_message(filters.command('delg') & filters.incoming & auth_filter)
async def deletegfilter(client, message):
    """Delete a specific global filter (admin only)"""
    try:
        cmd, text = message.text.split(" ", 1)
    except:
        await message.reply_text(
            "<i>Mention the gfiltername which you wanna delete!</i>\n\n"
            "<code>/delg gfiltername</code>\n\n"
            "Use /viewgfilters to view all available gfilters",
            quote=True
        )
        return

    query = text.lower()
    await delete_gfilter(message, query, 'gfilters')


@Client.on_message(filters.command('delallg') & filters.user(ADMINS))
async def delallgfilters(client, message):
    """Delete all global filters confirmation (admin only)"""
    await message.reply_text(
        f"Do you want to continue??",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="YES", callback_data="gfiltersdeleteallconfirm")],
            [InlineKeyboardButton(text="CANCEL", callback_data="gfiltersdeleteallcancel")]
        ]),
        quote=True
    )
