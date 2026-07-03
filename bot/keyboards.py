from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from core.config import WEBHOOK_URL

# --- REPLY KEYBOARDS ---

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔍 Browse")],
        [KeyboardButton(text="📝 Edit Info"), KeyboardButton(text="📸 Edit Media")],
        [KeyboardButton(text="👥 Profiles"), KeyboardButton(text="🔒 View Private Contacts")]
    ], resize_keyboard=True)

def edit_info_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✏️ Bio")], 
        [KeyboardButton(text="🌐 Public Contacts"), KeyboardButton(text="🔒 Private Contacts")],
        [KeyboardButton(text="🏠 View Active Profile")]
    ], resize_keyboard=True)

def edit_fsm_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Cancel"), KeyboardButton(text="🗑️ Clear Field")]
    ], resize_keyboard=True)

def browse_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⏩ Next Profile")],
        [KeyboardButton(text="🏠 View Active Profile")]
    ], resize_keyboard=True)

def manage_action_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🌟 Set Active"), KeyboardButton(text="👁️ Toggle Vis")],
        [KeyboardButton(text="🔄 Regen ID"), KeyboardButton(text="🗑️ Delete")],
        [KeyboardButton(text="🏠 View Active Profile")]
    ], resize_keyboard=True)

def profiles_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Create Profile")],
        [KeyboardButton(text="🗑️ Delete All But Active"), KeyboardButton(text="💣 Delete All Profiles")],
        [KeyboardButton(text="🏠 View Active Profile")]
    ], resize_keyboard=True)

def confirm_delete_all_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⚠️ YES, DELETE ALL PROFILES")],
        [KeyboardButton(text="❌ Cancel")]
    ], resize_keyboard=True)

# --- INLINE KEYBOARDS ---

def profile_inline_kb(profile_uuid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏷️ Tags", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=edit&profile_id={profile_uuid}")),
            InlineKeyboardButton(text="🎛️ Filters", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=filter&profile_id={profile_uuid}"))
        ]
    ])

def browse_inline_kb(target_uuid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💌 Request", callback_data=f"req_{target_uuid}"),
            InlineKeyboardButton(text="💌 Req + Msg", callback_data=f"reqmsg_{target_uuid}")
        ],
        [
            InlineKeyboardButton(text="🤝 Send Contact", callback_data=f"send_{target_uuid}"),
            InlineKeyboardButton(text="🤝 Send + Msg", callback_data=f"sendmsg_{target_uuid}")
        ]
    ])

def contact_decision_kb(req_id: str, is_sending: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if is_sending:
        buttons.append([InlineKeyboardButton(text="🤝 Share Mine Too", callback_data=f"accept_{req_id}")])
    else:
        buttons.append([
            InlineKeyboardButton(text="✅ Share Contact", callback_data=f"accept_{req_id}"),
            InlineKeyboardButton(text="🔄 Ask For Theirs", callback_data=f"counter_{req_id}")
        ])
    buttons.append([InlineKeyboardButton(text="❌ Hide/Decline", callback_data=f"decline_{req_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)