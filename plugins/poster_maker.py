"""
/poster command - Create custom posters for series using TMDB backdrops + logos.

Usage: /poster {seriesname}

Flow:
  1. Bot fetches random TMDB backdrop + logo for the series
  2. Merges them and sends the poster with series details
  3. Interactive buttons: [Change Image] [Change Logo]
                          [Change L Position] [Change L Size]
                          [Done]
  4. [Done] saves the poster as the series custom poster and replaces old one
"""

import os
import io
import uuid
import random
import logging
import asyncio
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

from database.series_db import db
from info import ADMINS, TMDB_API_KEY, IMGBB_API_KEY
from .series import build_series_info_text, upload_to_imgbb, auth_filter

logger = logging.getLogger(__name__)


# ============================================================================
# LOGO POSITIONS (9 positions as shown in the reference image)
# ============================================================================

LOGO_POSITIONS = {
    1: ("top",    "left"),
    2: ("top",    "center"),
    3: ("top",    "right"),
    4: ("middle", "left"),
    5: ("middle", "center"),
    6: ("middle", "right"),
    7: ("bottom", "left"),
    8: ("bottom", "center"),   # default
    9: ("bottom", "right"),
}

LOGO_POSITION_LABELS = {
    1: "↖ Top Left",
    2: "↑ Top Center",
    3: "↗ Top Right",
    4: "← Mid Left",
    5: "⊙ Center",
    6: "→ Mid Right",
    7: "↙ Bot Left",
    8: "↓ Bot Center",
    9: "↘ Bot Right",
}

LOGO_SIZES = {
    "small":       0.20,   # 20% of backdrop width
    "medium":      0.30,   # 30%
    "large":       0.45,   # 45%
    "extra_large": 0.60,   # 60%
}

LOGO_SIZE_LABELS = {
    "small":       "Small",
    "medium":      "Medium",
    "large":       "Large",
    "extra_large": "Extra Large",
}

# In-memory session storage for poster creation sessions
# Format: { user_id: { "series_id", "backdrops", "logos", "bg_idx", "logo_idx",
#                       "position", "size", "chat_id", "message_id" } }
_poster_sessions: dict = {}


# ============================================================================
# TMDB HELPERS
# ============================================================================

def _tmdb_get(endpoint: str, params: dict) -> dict:
    """Synchronous TMDB GET request."""
    params["api_key"] = TMDB_API_KEY
    try:
        r = requests.get(
            f"https://api.themoviedb.org/3/{endpoint}",
            params=params,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.error(f"TMDB request error ({endpoint}): {e}")
    return {}


def search_tmdb_tv(query: str):
    """Search TMDB for TV series and return list of results."""
    data = _tmdb_get("search/tv", {"query": query, "language": "en-US"})
    return data.get("results", [])


def get_backdrops(tmdb_id: int) -> list:
    """Get list of backdrop URLs (16:9) for a TMDB TV series."""
    data = _tmdb_get(f"tv/{tmdb_id}/images", {"include_image_language": "en,null"})
    backdrops = data.get("backdrops", [])
    urls = []
    for b in backdrops:
        path = b.get("file_path")
        if path:
            urls.append(f"https://image.tmdb.org/t/p/original{path}")
    return urls


def get_logos(tmdb_id: int) -> list:
    """Get list of logo PNG URLs for a TMDB TV series."""
    data = _tmdb_get(f"tv/{tmdb_id}/images", {"include_image_language": "en,null"})
    logos = data.get("logos", [])
    urls = []
    for logo in logos:
        path = logo.get("file_path")
        if path:
            urls.append(f"https://image.tmdb.org/t/p/original{path}")
    return urls


def download_image(url: str) -> Image.Image | None:
    """Download an image from URL and return PIL Image."""
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception as e:
        logger.error(f"Error downloading image {url}: {e}")
    return None


# ============================================================================
# POSTER COMPOSER
# ============================================================================

def compose_poster(
    backdrop_url: str,
    logo_url: str | None,
    position: int = 8,
    size: str = "medium",
) -> bytes | None:
    """
    Compose a 16:9 poster from backdrop + logo.
    Returns JPEG bytes or None on failure.
    """
    try:
        # Download backdrop
        bg = download_image(backdrop_url)
        if bg is None:
            return None

        # Resize to standard 1920x1080
        bg = bg.resize((1920, 1080), Image.LANCZOS)

        # Add subtle dark gradient overlay at the bottom for logo readability
        overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        gradient_height = 400
        for i in range(gradient_height):
            alpha = int((i / gradient_height) * 160)
            y = 1080 - gradient_height + i
            draw.line([(0, y), (1920, y)], fill=(0, 0, 0, alpha))

        bg = Image.alpha_composite(bg, overlay)

        if logo_url:
            logo = download_image(logo_url)
            if logo:
                # Calculate logo size
                scale = LOGO_SIZES.get(size, 0.30)
                max_w = int(1920 * scale)

                # Keep aspect ratio
                lw, lh = logo.size
                ratio = min(max_w / lw, 300 / lh)  # max height 300px
                new_w = int(lw * ratio)
                new_h = int(lh * ratio)
                logo = logo.resize((new_w, new_h), Image.LANCZOS)

                # Calculate position
                v_pos, h_pos = LOGO_POSITIONS.get(position, ("bottom", "center"))

                padding = 60

                if h_pos == "left":
                    x = padding
                elif h_pos == "right":
                    x = 1920 - new_w - padding
                else:  # center
                    x = (1920 - new_w) // 2

                if v_pos == "top":
                    y = padding
                elif v_pos == "middle":
                    y = (1080 - new_h) // 2
                else:  # bottom
                    y = 1080 - new_h - padding

                # Paste logo with transparency
                bg.paste(logo, (x, y), logo)

        # Convert to JPEG
        output = io.BytesIO()
        bg_rgb = bg.convert("RGB")
        bg_rgb.save(output, format="JPEG", quality=90)
        return output.getvalue()

    except Exception as e:
        logger.error(f"Error composing poster: {e}", exc_info=True)
        return None


# ============================================================================
# SESSION HELPERS
# ============================================================================

def get_session(user_id: int) -> dict | None:
    return _poster_sessions.get(user_id)


def set_session(user_id: int, data: dict):
    _poster_sessions[user_id] = data


def clear_session(user_id: int):
    _poster_sessions.pop(user_id, None)


# ============================================================================
# BUILD KEYBOARD
# ============================================================================

def build_poster_keyboard(series_id: str, user_id: int) -> InlineKeyboardMarkup:
    """Build the interactive poster keyboard."""
    uid = user_id
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼 Change Image",  callback_data=f"pm_chbg_{series_id}_{uid}"),
            InlineKeyboardButton("🔤 Change Logo",   callback_data=f"pm_chlogo_{series_id}_{uid}"),
        ],
        [
            InlineKeyboardButton("📍 Change L Position", callback_data=f"pm_pos_{series_id}_{uid}"),
            InlineKeyboardButton("📏 Change L Size",     callback_data=f"pm_size_{series_id}_{uid}"),
        ],
        [
            InlineKeyboardButton("✅ Done",           callback_data=f"pm_done_{series_id}_{uid}"),
        ],
    ])


def build_position_keyboard(series_id: str, user_id: int) -> InlineKeyboardMarkup:
    """9-position selector keyboard."""
    uid = user_id
    rows = []
    # 3 rows × 3 columns
    for row_start in [1, 4, 7]:
        row = []
        for pos in range(row_start, row_start + 3):
            row.append(InlineKeyboardButton(
                LOGO_POSITION_LABELS[pos],
                callback_data=f"pm_setpos_{series_id}_{uid}_{pos}"
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton("« Back", callback_data=f"pm_back_{series_id}_{uid}")])
    return InlineKeyboardMarkup(rows)


def build_size_keyboard(series_id: str, user_id: int) -> InlineKeyboardMarkup:
    """Logo size selector keyboard."""
    uid = user_id
    sizes = ["small", "medium", "large", "extra_large"]
    rows = [[
        InlineKeyboardButton(LOGO_SIZE_LABELS[s], callback_data=f"pm_setsize_{series_id}_{uid}_{s}")
    ] for s in sizes]
    rows.append([InlineKeyboardButton("« Back", callback_data=f"pm_back_{series_id}_{uid}")])
    return InlineKeyboardMarkup(rows)


# ============================================================================
# SEND / UPDATE POSTER MESSAGE
# ============================================================================

async def send_poster_message(
    client: Client,
    target,  # Message or chat_id
    series,
    session: dict,
    series_id: str,
    user_id: int,
    edit_message=None,
):
    """Compose and send/edit the poster message."""
    bg_url = session["backdrops"][session["bg_idx"]]
    logo_url = session["logos"][session["logo_idx"]] if session.get("logos") else None
    position = session.get("position", 8)
    size = session.get("size", "medium")

    # Compose
    img_bytes = await asyncio.get_event_loop().run_in_executor(
        None, compose_poster, bg_url, logo_url, position, size
    )

    if not img_bytes:
        err = "❌ Failed to compose poster. Please try again."
        if edit_message:
            await edit_message.reply_text(err)
        elif hasattr(target, "reply_text"):
            await target.reply_text(err)
        else:
            await client.send_message(target, err)
        return None

    caption = build_series_info_text(series)
    caption += f"\n<b>Position:</b> {LOGO_POSITION_LABELS.get(position, '—')}  |  <b>Size:</b> {LOGO_SIZE_LABELS.get(size, '—')}"

    keyboard = build_poster_keyboard(series_id, user_id)

    # Send as photo
    photo_io = io.BytesIO(img_bytes)
    photo_io.name = "poster.jpg"

    if edit_message:
        # We need to send a new photo message (can't edit photo with Pyrogram easily)
        try:
            await edit_message.delete()
        except Exception:
            pass
        chat_id = edit_message.chat.id if hasattr(edit_message, 'chat') else edit_message
        sent = await client.send_photo(
            chat_id=chat_id,
            photo=photo_io,
            caption=caption,
            reply_markup=keyboard,
        )
    elif hasattr(target, "reply_photo"):
        sent = await target.reply_photo(
            photo=photo_io,
            caption=caption,
            reply_markup=keyboard,
        )
    else:
        sent = await client.send_photo(
            chat_id=target,
            photo=photo_io,
            caption=caption,
            reply_markup=keyboard,
        )

    return sent


# ============================================================================
# /poster COMMAND
# ============================================================================

@Client.on_message(filters.private & auth_filter & filters.command("poster"))
async def poster_command(client: Client, message: Message):
    """/poster {seriesname} — Create a custom poster for the series."""
    if len(message.command) < 2:
        await message.reply_text(
            "❌ Please provide a series name!\n\n"
            "<b>Usage:</b> <code>/poster {seriesname}</code>\n"
            "<b>Example:</b> <code>/poster Stranger Things</code>"
        )
        return

    series_name = " ".join(message.command[1:])
    user_id = message.from_user.id

    status_msg = await message.reply_text(f"🔍 Searching for <b>{series_name}</b>...")

    # Find series in DB
    all_series = await db.get_all_series()
    found_series = None
    for s in all_series:
        if s.get("title", "").lower() == series_name.lower():
            found_series = s
            break

    if not found_series:
        # Try partial match
        for s in all_series:
            if series_name.lower() in s.get("title", "").lower():
                found_series = s
                break

    if not found_series:
        await status_msg.edit_text(
            f"❌ Series <b>'{series_name}'</b> not found in database!\n\n"
            "Use <code>/allseries</code> to see all saved series."
        )
        return

    series_id = str(found_series["_id"])
    series_title = found_series.get("title", "Unknown")
    imdb_id = found_series.get("imdb_id", "")

    await status_msg.edit_text(f"🎬 Fetching TMDB data for <b>{series_title}</b>...")

    # Search TMDB for this series
    tmdb_id = None

    # Try to get TMDB ID from imdb_id stored in DB (format: tmdb_XXXXX)
    if imdb_id and imdb_id.startswith("tmdb_"):
        try:
            tmdb_id = int(imdb_id.replace("tmdb_", ""))
        except ValueError:
            pass

    # If not found, search TMDB
    if not tmdb_id:
        results = await asyncio.get_event_loop().run_in_executor(
            None, search_tmdb_tv, series_title
        )
        if results:
            tmdb_id = results[0]["id"]

    if not tmdb_id:
        await status_msg.edit_text(
            f"❌ Could not find <b>{series_title}</b> on TMDB!\n"
            "Make sure the series was added from TMDB source."
        )
        return

    # Fetch backdrops and logos
    backdrops, logos = await asyncio.gather(
        asyncio.get_event_loop().run_in_executor(None, get_backdrops, tmdb_id),
        asyncio.get_event_loop().run_in_executor(None, get_logos, tmdb_id),
    )

    if not backdrops:
        await status_msg.edit_text(
            f"❌ No backdrop images found for <b>{series_title}</b> on TMDB!"
        )
        return

    # Shuffle so [Change Image] feels random
    random.shuffle(backdrops)
    if logos:
        random.shuffle(logos)

    # Store session
    session = {
        "series_id": series_id,
        "backdrops": backdrops,
        "logos": logos if logos else [],
        "bg_idx": 0,
        "logo_idx": 0,
        "position": 8,       # default: bottom center
        "size": "medium",
        "chat_id": message.chat.id,
    }
    set_session(user_id, session)

    await status_msg.edit_text("🎨 Composing poster...")

    sent = await send_poster_message(
        client=client,
        target=message,
        series=found_series,
        session=session,
        series_id=series_id,
        user_id=user_id,
        edit_message=None,
    )

    if sent:
        session["message_id"] = sent.id
        set_session(user_id, session)

    try:
        await status_msg.delete()
    except Exception:
        pass


# ============================================================================
# POSTER CALLBACK HANDLER
# ============================================================================

@Client.on_callback_query(filters.regex(r"^pm_"))
async def poster_callback(client: Client, callback_query: CallbackQuery):
    """Handle all poster maker callbacks."""
    data = callback_query.data
    user_id = callback_query.from_user.id

    # Parse callback: pm_ACTION_seriesid_userid[_extra]
    parts = data.split("_")
    # parts[0] = "pm", parts[1] = action, parts[2] = series_id, parts[3] = owner_uid
    # For setpos/setsize: parts[4] = value

    if len(parts) < 4:
        await callback_query.answer("Invalid action!", show_alert=True)
        return

    action = parts[1]
    series_id = parts[2]
    owner_uid = int(parts[3])

    # Only the owner can interact
    if user_id != owner_uid:
        await callback_query.answer("This is not your poster session!", show_alert=True)
        return

    session = get_session(user_id)
    if not session:
        await callback_query.answer("Session expired! Please use /poster again.", show_alert=True)
        return

    series = await db.get_series(series_id)
    if not series:
        await callback_query.answer("Series not found!", show_alert=True)
        return

    msg = callback_query.message

    # ─── Change Background Image ───────────────────────────────────────────
    if action == "chbg":
        if not session["backdrops"]:
            await callback_query.answer("No more backdrops available!", show_alert=True)
            return

        # Advance to next backdrop (cycle)
        session["bg_idx"] = (session["bg_idx"] + 1) % len(session["backdrops"])
        set_session(user_id, session)

        await callback_query.answer("🖼 Changing background...")
        await msg.delete()
        sent = await send_poster_message(
            client=client,
            target=msg.chat.id,
            series=series,
            session=session,
            series_id=series_id,
            user_id=user_id,
        )
        if sent:
            session["message_id"] = sent.id
            set_session(user_id, session)

    # ─── Change Logo ────────────────────────────────────────────────────────
    elif action == "chlogo":
        if not session["logos"]:
            await callback_query.answer("No logos available for this series!", show_alert=True)
            return

        session["logo_idx"] = (session["logo_idx"] + 1) % len(session["logos"])
        set_session(user_id, session)

        await callback_query.answer("🔤 Changing logo...")
        await msg.delete()
        sent = await send_poster_message(
            client=client,
            target=msg.chat.id,
            series=series,
            session=session,
            series_id=series_id,
            user_id=user_id,
        )
        if sent:
            session["message_id"] = sent.id
            set_session(user_id, session)

    # ─── Show Position Selector ─────────────────────────────────────────────
    elif action == "pos":
        await callback_query.answer()
        await msg.edit_reply_markup(reply_markup=build_position_keyboard(series_id, user_id))

    # ─── Set Position ────────────────────────────────────────────────────────
    elif action == "setpos":
        if len(parts) < 5:
            await callback_query.answer("Invalid position!", show_alert=True)
            return
        try:
            pos = int(parts[4])
        except ValueError:
            await callback_query.answer("Invalid position!", show_alert=True)
            return

        session["position"] = pos
        set_session(user_id, session)

        await callback_query.answer(f"📍 Position set to {LOGO_POSITION_LABELS.get(pos, pos)}")
        await msg.delete()
        sent = await send_poster_message(
            client=client,
            target=msg.chat.id,
            series=series,
            session=session,
            series_id=series_id,
            user_id=user_id,
        )
        if sent:
            session["message_id"] = sent.id
            set_session(user_id, session)

    # ─── Show Size Selector ──────────────────────────────────────────────────
    elif action == "size":
        await callback_query.answer()
        await msg.edit_reply_markup(reply_markup=build_size_keyboard(series_id, user_id))

    # ─── Set Size ────────────────────────────────────────────────────────────
    elif action == "setsize":
        if len(parts) < 5:
            await callback_query.answer("Invalid size!", show_alert=True)
            return
        size = parts[4]
        if size not in LOGO_SIZES:
            await callback_query.answer("Invalid size!", show_alert=True)
            return

        session["size"] = size
        set_session(user_id, session)

        await callback_query.answer(f"📏 Size set to {LOGO_SIZE_LABELS.get(size, size)}")
        await msg.delete()
        sent = await send_poster_message(
            client=client,
            target=msg.chat.id,
            series=series,
            session=session,
            series_id=series_id,
            user_id=user_id,
        )
        if sent:
            session["message_id"] = sent.id
            set_session(user_id, session)

    # ─── Back to Main Poster Keyboard ────────────────────────────────────────
    elif action == "back":
        await callback_query.answer()
        await msg.edit_reply_markup(reply_markup=build_poster_keyboard(series_id, user_id))

    # ─── Done — Save as series poster ────────────────────────────────────────
    elif action == "done":
        await callback_query.answer("⏳ Saving poster...")

        bg_url = session["backdrops"][session["bg_idx"]]
        logo_url = session["logos"][session["logo_idx"]] if session.get("logos") else None
        position = session.get("position", 8)
        size = session.get("size", "medium")

        # Compose final poster
        await msg.edit_caption(caption="⏳ Finalising and uploading poster...")

        img_bytes = await asyncio.get_event_loop().run_in_executor(
            None, compose_poster, bg_url, logo_url, position, size
        )

        if not img_bytes:
            await msg.edit_caption(caption="❌ Failed to compose poster!")
            return

        # Save to temp file and upload to ImgBB
        tmp_path = f"/tmp/poster_{series_id}_{uuid.uuid4().hex[:8]}.jpg"
        with open(tmp_path, "wb") as f:
            f.write(img_bytes)

        poster_url = await upload_to_imgbb(tmp_path)

        try:
            os.remove(tmp_path)
        except Exception:
            pass

        if not poster_url:
            await msg.edit_caption(caption="❌ Failed to upload poster to ImgBB! Please try again.")
            return

        # Save to DB
        await db.update_series_poster(series_id, poster_url)

        series_title = series.get("title", "Unknown")
        clear_session(user_id)

        # Delete the poster preview message
        try:
            await msg.delete()
        except Exception:
            pass

        await client.send_message(
            chat_id=callback_query.message.chat.id,
            text=f"<b>{series_title}</b> poster updated ✅",
        )

    else:
        await callback_query.answer("Unknown action!", show_alert=True)
