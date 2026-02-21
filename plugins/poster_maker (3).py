"""
/poster {seriesname} — Admins & Auth Users only.

Navigation is fully dynamic — every button edits the SAME message.
No delete + resend ever (except Done which cleans up).

Button flow:
  Main view:
    [🖼 Change Image]  [🔤 Change Logo]
    [📍 Change L Position]  [📏 Change L Size]
    [✅ Done]

  Change Image view:  (numbered grid, 5 per row)
    [1][2][3][4][5]
    [6][7][8][9][10]  ...etc
    [« Back]

  Change Logo view:  same numbered grid
    [1][2][3][4][5]
    ...
    [« Back]

  Position view:  3×3 grid
    [↖][↑][↗]
    [←][⊙][→]
    [↙][↓][↘]
    [« Back]

  Size view:
    [Small][Medium][Large][Extra Large]
    [« Back]
"""

import os
import io
import uuid
import random
import logging
import asyncio
import requests
from PIL import Image, ImageDraw

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, Message, InputMediaPhoto,
)

from database.series_db import db
from info import TMDB_API_KEY, IMGBB_API_KEY
from .series import build_series_info_text, upload_to_imgbb, auth_filter

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

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
    1: "↖",  2: "↑",  3: "↗",
    4: "←",  5: "⊙",  6: "→",
    7: "↙",  8: "↓",  9: "↘",
}

LOGO_POSITION_FULL = {
    1: "Top Left",    2: "Top Center",    3: "Top Right",
    4: "Mid Left",    5: "Center",        6: "Mid Right",
    7: "Bot Left",    8: "Bot Center",    9: "Bot Right",
}

LOGO_SIZES = {
    "small":       0.20,
    "medium":      0.30,
    "large":       0.45,
    "extra_large": 0.60,
}

LOGO_SIZE_LABELS = {
    "small":       "Small",
    "medium":      "Medium",
    "large":       "Large",
    "extra_large": "Extra Large",
}

# In-memory sessions  { user_id: { ...session data... } }
_sessions: dict = {}


# ─────────────────────────────────────────────────────────────────────────────
# TMDB HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _tmdb_get(endpoint: str, params: dict) -> dict:
    params["api_key"] = TMDB_API_KEY
    try:
        r = requests.get(
            f"https://api.themoviedb.org/3/{endpoint}",
            params=params, timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.error(f"TMDB error [{endpoint}]: {e}")
    return {}


def search_tmdb_tv(query: str) -> list:
    return _tmdb_get("search/tv", {"query": query, "language": "en-US"}).get("results", [])


def get_backdrops_and_logos(tmdb_id: int) -> tuple:
    data = _tmdb_get(f"tv/{tmdb_id}/images", {"include_image_language": "en,null"})
    backdrops = [
        f"https://image.tmdb.org/t/p/original{b['file_path']}"
        for b in data.get("backdrops", []) if b.get("file_path")
    ]
    logos = [
        f"https://image.tmdb.org/t/p/original{l['file_path']}"
        for l in data.get("logos", []) if l.get("file_path")
    ]
    return backdrops, logos


def download_image(url: str):
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception as e:
        logger.error(f"Download error [{url}]: {e}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# POSTER COMPOSER
# ─────────────────────────────────────────────────────────────────────────────

def compose_poster(backdrop_url: str, logo_url, position: int = 8, size: str = "medium"):
    """Returns JPEG bytes or None."""
    try:
        bg = download_image(backdrop_url)
        if not bg:
            return None

        bg = bg.resize((1920, 1080), Image.LANCZOS)

        # Dark gradient at bottom for logo readability
        overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        gh = 400
        for i in range(gh):
            alpha = int((i / gh) * 160)
            y = 1080 - gh + i
            draw.line([(0, y), (1920, y)], fill=(0, 0, 0, alpha))
        bg = Image.alpha_composite(bg, overlay)

        if logo_url:
            logo = download_image(logo_url)
            if logo:
                scale = LOGO_SIZES.get(size, 0.30)
                max_w = int(1920 * scale)
                lw, lh = logo.size
                ratio = min(max_w / lw, 300 / lh)
                nw, nh = int(lw * ratio), int(lh * ratio)
                logo = logo.resize((nw, nh), Image.LANCZOS)

                v_pos, h_pos = LOGO_POSITIONS.get(position, ("bottom", "center"))
                pad = 60

                x = pad if h_pos == "left" else (1920 - nw - pad if h_pos == "right" else (1920 - nw) // 2)
                y = pad if v_pos == "top" else ((1080 - nh) // 2 if v_pos == "middle" else 1080 - nh - pad)

                bg.paste(logo, (x, y), logo)

        rgb = bg.convert("RGB")
        return _compress_to_limit(rgb, max_kb=120)

    except Exception as e:
        logger.error(f"compose_poster error: {e}", exc_info=True)
        return None


def _compress_to_limit(img: Image.Image, max_kb: int = 120) -> bytes:
    """
    Save at high quality. Only compresses if needed (e.g. upload fails).
    """
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# SESSION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_session(uid: int):
    return _sessions.get(uid)

def set_session(uid: int, data: dict):
    _sessions[uid] = data

def clear_session(uid: int):
    _sessions.pop(uid, None)


# ─────────────────────────────────────────────────────────────────────────────
# KEYBOARD BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _num_grid(items: list, cb_prefix: str, back_cb: str) -> InlineKeyboardMarkup:
    """
    Build a numbered grid keyboard (5 per row) for a list of items.
    cb_prefix example: "pm_selimg_abc123_123456"  → button cb = "pm_selimg_abc123_123456_0"
    Numbers shown are 1-based (display), index is 0-based (stored).
    """
    rows = []
    row = []
    for idx in range(len(items)):
        row.append(InlineKeyboardButton(
            str(idx + 1),
            callback_data=f"{cb_prefix}_{idx}"
        ))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("« Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def kb_main(sid: str, uid: int) -> InlineKeyboardMarkup:
    u = uid
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🖼 Change Image",      callback_data=f"pm_chbg_{sid}_{u}"),
            InlineKeyboardButton("🔤 Change Logo",       callback_data=f"pm_chlogo_{sid}_{u}"),
        ],
        [
            InlineKeyboardButton("📍 Change L Position", callback_data=f"pm_pos_{sid}_{u}"),
            InlineKeyboardButton("📏 Change L Size",     callback_data=f"pm_size_{sid}_{u}"),
        ],
        [
            InlineKeyboardButton("✅ Done",              callback_data=f"pm_done_{sid}_{u}"),
        ],
    ])


def kb_images(sid: str, uid: int, backdrops: list) -> InlineKeyboardMarkup:
    return _num_grid(
        backdrops,
        cb_prefix=f"pm_selimg_{sid}_{uid}",
        back_cb=f"pm_back_{sid}_{uid}",
    )


def kb_logos(sid: str, uid: int, logos: list) -> InlineKeyboardMarkup:
    base = _num_grid(
        logos,
        cb_prefix=f"pm_sellogo_{sid}_{uid}",
        back_cb=f"pm_back_{sid}_{uid}",
    )
    # Insert "No Logo" button as the first row
    no_logo_row = [InlineKeyboardButton("🚫 No Logo", callback_data=f"pm_nologo_{sid}_{uid}")]
    return InlineKeyboardMarkup([no_logo_row] + list(base.inline_keyboard))


def kb_position(sid: str, uid: int) -> InlineKeyboardMarkup:
    u = uid
    rows = []
    for row_start in [1, 4, 7]:
        rows.append([
            InlineKeyboardButton(
                LOGO_POSITION_LABELS[p],
                callback_data=f"pm_setpos_{sid}_{u}_{p}"
            )
            for p in range(row_start, row_start + 3)
        ])
    rows.append([InlineKeyboardButton("« Back", callback_data=f"pm_back_{sid}_{u}")])
    return InlineKeyboardMarkup(rows)


def kb_size(sid: str, uid: int) -> InlineKeyboardMarkup:
    u = uid
    rows = [
        [InlineKeyboardButton(LOGO_SIZE_LABELS[s], callback_data=f"pm_setsize_{sid}_{u}_{s}")]
        for s in ["small", "medium", "large", "extra_large"]
    ]
    rows.append([InlineKeyboardButton("« Back", callback_data=f"pm_back_{sid}_{u}")])
    return InlineKeyboardMarkup(rows)


# ─────────────────────────────────────────────────────────────────────────────
# CAPTION
# ─────────────────────────────────────────────────────────────────────────────

def _caption(series: dict, session: dict) -> str:
    pos = session.get("position", 8)
    size = session.get("size", "medium")
    bg_idx = session.get("bg_idx", 0)
    logo_idx = session.get("logo_idx", 0)
    total_bg = len(session.get("backdrops", []))
    total_logo = len(session.get("logos", []))

    text = build_series_info_text(series)
    text += f"\n<b>Image:</b> {bg_idx + 1}/{total_bg}"
    if total_logo:
        text += f"  |  <b>Logo:</b> {logo_idx + 1}/{total_logo}"
    text += f"\n<b>Position:</b> {LOGO_POSITION_FULL.get(pos, '—')}  |  <b>Size:</b> {LOGO_SIZE_LABELS.get(size, '—')}"
    return text


# ─────────────────────────────────────────────────────────────────────────────
# CORE: EDIT POSTER IN PLACE
# ─────────────────────────────────────────────────────────────────────────────

async def _edit_poster(client: Client, msg: Message, series: dict, session: dict, sid: str, uid: int):
    """
    Compose and edit the existing message with the new poster.
    NEVER deletes and resends — always edits in place.
    """
    bg_url = session["backdrops"][session["bg_idx"]]
    if session.get("no_logo"):
        logo_url = None
    else:
        logo_url = session["logos"][session["logo_idx"]] if session.get("logos") else None
    position = session.get("position", 8)
    size = session.get("size", "medium")

    img_bytes = await asyncio.get_event_loop().run_in_executor(
        None, compose_poster, bg_url, logo_url, position, size
    )

    if not img_bytes:
        await msg.edit_caption(caption="❌ Failed to compose poster. Please try again.")
        return

    photo_io = io.BytesIO(img_bytes)
    photo_io.name = "poster.jpg"

    await msg.edit_media(
        media=InputMediaPhoto(media=photo_io, caption=_caption(series, session)),
        reply_markup=kb_main(sid, uid),
    )


# ─────────────────────────────────────────────────────────────────────────────
# /poster COMMAND
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.private & auth_filter & filters.command("poster"))
async def poster_command(client: Client, message: Message):
    """/poster {seriesname} — Admins & Auth Users only."""
    if len(message.command) < 2:
        await message.reply_text(
            "❌ Please provide a series name!\n\n"
            "<b>Usage:</b> <code>/poster {seriesname}</code>\n"
            "<b>Example:</b> <code>/poster Stranger Things</code>"
        )
        return

    series_name = " ".join(message.command[1:])
    user_id = message.from_user.id

    status = await message.reply_text(f"🔍 Searching for <b>{series_name}</b>...")

    # Find in DB — exact match first, then partial
    all_series = await db.get_all_series()
    found = None
    for s in all_series:
        if s.get("title", "").lower() == series_name.lower():
            found = s
            break
    if not found:
        for s in all_series:
            if series_name.lower() in s.get("title", "").lower():
                found = s
                break

    if not found:
        await status.edit_text(
            f"❌ Series <b>'{series_name}'</b> not found in database!\n\n"
            "Use <code>/allseries</code> to see all saved series."
        )
        return

    sid = str(found["_id"])
    title = found.get("title", "Unknown")
    imdb_id = found.get("imdb_id", "")

    await status.edit_text(f"🎬 Fetching TMDB data for <b>{title}</b>...")

    # Resolve TMDB ID
    tmdb_id = None
    if imdb_id and imdb_id.startswith("tmdb_"):
        try:
            tmdb_id = int(imdb_id.replace("tmdb_", ""))
        except ValueError:
            pass
    if not tmdb_id:
        results = await asyncio.get_event_loop().run_in_executor(None, search_tmdb_tv, title)
        if results:
            tmdb_id = results[0]["id"]

    if not tmdb_id:
        await status.edit_text(f"❌ Could not find <b>{title}</b> on TMDB!")
        return

    await status.edit_text("🖼 Fetching backdrops and logos...")

    backdrops, logos = await asyncio.get_event_loop().run_in_executor(
        None, get_backdrops_and_logos, tmdb_id
    )

    if not backdrops:
        await status.edit_text(f"❌ No backdrop images found for <b>{title}</b> on TMDB!")
        return

    random.shuffle(backdrops)
    if logos:
        random.shuffle(logos)

    session = {
        "series_id": sid,
        "backdrops": backdrops,
        "logos": logos,
        "bg_idx": 0,
        "logo_idx": 0,
        "position": 8,
        "size": "medium",
    }
    set_session(user_id, session)

    await status.edit_text("🎨 Composing poster...")

    # Compose initial poster
    img_bytes = await asyncio.get_event_loop().run_in_executor(
        None, compose_poster,
        backdrops[0], logos[0] if logos else None, 8, "medium"
    )

    if not img_bytes:
        await status.edit_text("❌ Failed to compose poster. Please try again.")
        clear_session(user_id)
        return

    photo_io = io.BytesIO(img_bytes)
    photo_io.name = "poster.jpg"

    sent = await message.reply_photo(
        photo=photo_io,
        caption=_caption(found, session),
        reply_markup=kb_main(sid, user_id),
    )
    session["message_id"] = sent.id
    set_session(user_id, session)

    try:
        await status.delete()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACK HANDLER
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^pm_"))
async def poster_callback(client: Client, cq: CallbackQuery):
    """
    All poster maker interactions.
    Dynamic navigation — always edits the same message.
    """
    data = cq.data
    uid = cq.from_user.id

    # callback format:  pm_ACTION_sid_owneruid[_extra]
    # series_id may contain hyphens, so split carefully
    # prefix = "pm_ACTION_"  →  then "sid_owneruid[_extra]"
    try:
        # parts[0]=pm  parts[1]=action  parts[2]=sid  parts[3]=owneruid  parts[4?]=extra
        parts = data.split("_")
        action = parts[1]
        sid = parts[2]
        owner_uid = int(parts[3])
    except (IndexError, ValueError):
        await cq.answer("Invalid action!", show_alert=True)
        return

    # Button lock
    if uid != owner_uid:
        await cq.answer("This is not your session!", show_alert=True)
        return

    session = get_session(uid)
    if not session:
        await cq.answer("Session expired! Use /poster again.", show_alert=True)
        return

    series = await db.get_series(sid)
    if not series:
        await cq.answer("Series not found!", show_alert=True)
        return

    msg = cq.message

    # ── Show numbered image picker ──────────────────────────────────────────
    if action == "chbg":
        await cq.answer()
        backdrops = session["backdrops"]
        if not backdrops:
            await cq.answer("No backdrops available!", show_alert=True)
            return
        await msg.edit_reply_markup(reply_markup=kb_images(sid, uid, backdrops))

    # ── Select specific image by index ──────────────────────────────────────
    elif action == "selimg":
        try:
            idx = int(parts[4])
        except (IndexError, ValueError):
            await cq.answer("Invalid selection!", show_alert=True)
            return
        if idx < 0 or idx >= len(session["backdrops"]):
            await cq.answer("Invalid image number!", show_alert=True)
            return
        session["bg_idx"] = idx
        set_session(uid, session)
        await cq.answer(f"🖼 Image {idx + 1} selected")
        await _edit_poster(client, msg, series, session, sid, uid)

    # ── Show numbered logo picker ────────────────────────────────────────────
    elif action == "chlogo":
        logos = session.get("logos", [])
        if not logos:
            await cq.answer("No logos available for this series!", show_alert=True)
            return
        await cq.answer()
        await msg.edit_reply_markup(reply_markup=kb_logos(sid, uid, logos))

    # ── Select specific logo by index ───────────────────────────────────────
    elif action == "sellogo":
        try:
            idx = int(parts[4])
        except (IndexError, ValueError):
            await cq.answer("Invalid selection!", show_alert=True)
            return
        logos = session.get("logos", [])
        if idx < 0 or idx >= len(logos):
            await cq.answer("Invalid logo number!", show_alert=True)
            return
        session["logo_idx"] = idx
        session["no_logo"] = False
        set_session(uid, session)
        await cq.answer(f"🔤 Logo {idx + 1} selected")
        await _edit_poster(client, msg, series, session, sid, uid)

    # ── No Logo ──────────────────────────────────────────────────────────────
    elif action == "nologo":
        session["no_logo"] = True
        set_session(uid, session)
        await cq.answer("🚫 No logo will be used")
        await _edit_poster(client, msg, series, session, sid, uid)

    # ── Show position picker ─────────────────────────────────────────────────
    elif action == "pos":
        await cq.answer()
        await msg.edit_reply_markup(reply_markup=kb_position(sid, uid))

    # ── Set position ─────────────────────────────────────────────────────────
    elif action == "setpos":
        try:
            pos = int(parts[4])
        except (IndexError, ValueError):
            await cq.answer("Invalid position!", show_alert=True)
            return
        session["position"] = pos
        set_session(uid, session)
        await cq.answer(f"📍 {LOGO_POSITION_FULL.get(pos, pos)}")
        await _edit_poster(client, msg, series, session, sid, uid)

    # ── Show size picker ─────────────────────────────────────────────────────
    elif action == "size":
        await cq.answer()
        await msg.edit_reply_markup(reply_markup=kb_size(sid, uid))

    # ── Set size ─────────────────────────────────────────────────────────────
    elif action == "setsize":
        try:
            size = parts[4]
        except IndexError:
            await cq.answer("Invalid size!", show_alert=True)
            return
        if size not in LOGO_SIZES:
            await cq.answer("Invalid size!", show_alert=True)
            return
        session["size"] = size
        set_session(uid, session)
        await cq.answer(f"📏 {LOGO_SIZE_LABELS.get(size, size)}")
        await _edit_poster(client, msg, series, session, sid, uid)

    # ── Back to main keyboard ────────────────────────────────────────────────
    elif action == "back":
        await cq.answer()
        await msg.edit_reply_markup(reply_markup=kb_main(sid, uid))

    # ── Done — upload & save ─────────────────────────────────────────────────
    elif action == "done":
        await cq.answer("⏳ Saving poster...")
        await msg.edit_caption(caption="⏳ Finalising and uploading poster...")

        bg_url = session["backdrops"][session["bg_idx"]]
        if session.get("no_logo"):
            logo_url = None
        else:
            logo_url = session["logos"][session["logo_idx"]] if session.get("logos") else None
        position = session.get("position", 8)
        size = session.get("size", "medium")

        img_bytes = await asyncio.get_event_loop().run_in_executor(
            None, compose_poster, bg_url, logo_url, position, size
        )

        if not img_bytes:
            await msg.edit_caption(caption="❌ Failed to compose poster!")
            return

        tmp = f"/tmp/poster_{sid}_{uuid.uuid4().hex[:8]}.jpg"
        with open(tmp, "wb") as f:
            f.write(img_bytes)

        poster_url = await upload_to_imgbb(tmp)

        try:
            os.remove(tmp)
        except Exception:
            pass

        if not poster_url:
            await msg.edit_caption(caption="❌ Failed to upload to ImgBB! Please try again.")
            return

        await db.update_series_poster(sid, poster_url)

        series_title = series.get("title", "Unknown")
        clear_session(uid)

        try:
            await msg.delete()
        except Exception:
            pass

        await client.send_message(
            chat_id=cq.message.chat.id,
            text=f"<b>{series_title}</b> poster updated ✅",
        )

    else:
        await cq.answer("Unknown action!", show_alert=True)
