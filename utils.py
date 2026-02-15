import re
from typing import Tuple, List
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram import enums

# Button URL regex pattern
BTN_URL_REGEX = re.compile(
    r"(\[([^\[]+?)\]\((buttonurl|buttonalert):(?:/{0,2})(.+?)(:same)?\))"
)

SMART_OPEN = '"'
SMART_CLOSE = '"'
START_CHAR = ('\'', '"', SMART_OPEN)


def get_file_id(msg: Message):
    """Extract file ID from message media"""
    if msg.media:
        for message_type in (
            "photo",
            "animation",
            "audio",
            "document",
            "video",
            "video_note",
            "voice",
            "sticker"
        ):
            obj = getattr(msg, message_type)
            if obj:
                setattr(obj, "message_type", message_type)
                return obj
    return None


def split_quotes(text: str) -> List:
    """
    Split text by quotes to separate filter name and content
    Supports both regular quotes and smart quotes
    Example: 'hello "This is content"' -> ['hello', 'This is content']
    """
    if text.startswith(START_CHAR):
        counter = 1  # ignore first char -> is some kind of quote
        while counter < len(text):
            if text[counter] == "\\":
                counter += 1
            elif text[counter] == text[0] or (text[0] == SMART_OPEN and text[counter] == SMART_CLOSE):
                break
            counter += 1
        else:
            return text.split(None, 1)

        # 1 to avoid starting quote, and counter is exclusive so avoids ending
        key = remove_escapes(text[1:counter].strip())
        # index will be in range, or <code>else</code> would have been executed and returned
        rest = text[counter + 1:].strip()
        if not key:
            key = text[0] + text[0]
        return list(filter(None, [key, rest]))
    
    # Fallback to simple quote splitting
    if '"' in text:
        parts = text.split('"')
        if len(parts) >= 3:
            return [parts[0].strip(), parts[1]]
        elif len(parts) == 2:
            return [parts[0].strip(), parts[1]]
    return [text]


def remove_escapes(text: str) -> str:
    """Remove escape characters from text"""
    res = ""
    is_escaped = False
    for counter in range(len(text)):
        if is_escaped:
            res += text[counter]
            is_escaped = False
        elif text[counter] == "\\":
            is_escaped = True
        else:
            res += text[counter]
    return res


def parser(text, keyword):
    """
    Parse filter content to extract buttons and alerts
    Supports button format: [Button Text](buttonurl:URL) or [Button Text](buttonurl:URL:same)
    Supports alert format: [Button Text](buttonalert:Alert Text)
    
    Returns: (reply_text, buttons, alerts)
    """
    if "buttonalert" in text:
        text = (text.replace("\n", "\\n").replace("\t", "\\t"))
    buttons = []
    note_data = ""
    prev = 0
    i = 0
    alerts = []
    for match in BTN_URL_REGEX.finditer(text):
        # Check if btnurl is escaped
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        # if even, not escaped -> create button
        if n_escapes % 2 == 0:
            note_data += text[prev:match.start(1)]
            prev = match.end(1)
            if match.group(3) == "buttonalert":
                # create a button with alert callback
                if bool(match.group(5)) and buttons:
                    buttons[-1].append(InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"alertmessage:{i}:{keyword}"
                    ))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"alertmessage:{i}:{keyword}"
                    )])
                i += 1
                alerts.append(match.group(4))
            elif bool(match.group(5)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                ))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                )])

        else:
            note_data += text[prev:to_check]
            prev = match.start(1) - 1
    else:
        note_data += text[prev:]

    try:
        return note_data, buttons, alerts
    except:
        return note_data, buttons, None


def gfilterparser(text, keyword):
    """
    Parse gfilter content - similar to parser but for global filters
    Supports button format: [Button Text](buttonurl:URL) or [Button Text](buttonurl:URL:same)
    Supports alert format: [Button Text](buttonalert:Alert Text)
    
    Returns: (reply_text, buttons, alerts)
    """
    if "buttonalert" in text:
        text = (text.replace("\n", "\\n").replace("\t", "\\t"))
    buttons = []
    note_data = ""
    prev = 0
    i = 0
    alerts = []
    for match in BTN_URL_REGEX.finditer(text):
        # Check if btnurl is escaped
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        # if even, not escaped -> create button
        if n_escapes % 2 == 0:
            note_data += text[prev:match.start(1)]
            prev = match.end(1)
            if match.group(3) == "buttonalert":
                # create a button with gfilter alert callback
                if bool(match.group(5)) and buttons:
                    buttons[-1].append(InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"gfilteralert:{i}:{keyword}"
                    ))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"gfilteralert:{i}:{keyword}"
                    )])
                i += 1
                alerts.append(match.group(4))
            elif bool(match.group(5)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                ))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                )])

        else:
            note_data += text[prev:to_check]
            prev = match.start(1) - 1
    else:
        note_data += text[prev:]

    try:
        return note_data, buttons, alerts
    except:
        return note_data, buttons, None


def parse_buttons(buttons_str: str) -> InlineKeyboardMarkup:
    """
    Convert button string back to InlineKeyboardMarkup
    """
    try:
        if buttons_str == "[]" or not buttons_str:
            return None
        
        # Parse the string representation back to buttons
        buttons_str = buttons_str.replace("InlineKeyboardButton", "").replace("'", '"')
        buttons_data = eval(buttons_str)
        
        if not buttons_data:
            return None
        
        keyboard = []
        for row in buttons_data:
            button_row = []
            for btn in row:
                if isinstance(btn, dict):
                    if 'url' in btn:
                        button_row.append(InlineKeyboardButton(btn['text'], url=btn['url']))
                    elif 'callback_data' in btn:
                        button_row.append(InlineKeyboardButton(btn['text'], callback_data=btn['callback_data']))
            if button_row:
                keyboard.append(button_row)
        
        return InlineKeyboardMarkup(keyboard) if keyboard else None
    except:
        return None


def get_size(size):
    """Get size in readable format"""
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])


def humanbytes(size):
    """Get size in human readable format"""
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'


def list_to_str(k):
    """Convert list to string"""
    if not k:
        return "N/A"
    elif len(k) == 1:
        return str(k[0])
    else:
        return ' '.join(f'{elem}, ' for elem in k)


def split_list(l, n):
    """Split list into chunks of size n"""
    for i in range(0, len(l), n):
        yield l[i:i + n]
