from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from core.config import WEBHOOK_URL

# --- REPLY KEYBOARDS (Нижние кнопки меню) ---

def main_menu_kb() -> ReplyKeyboardMarkup:
    """Упрощенное главное меню (кнопки Web App перенесены в Inline под саму анкету)"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔍 Browse")],
        [KeyboardButton(text="📝 Edit Info"), KeyboardButton(text="📸 Edit Media")],
        [KeyboardButton(text="👥 Profiles"), KeyboardButton(text="🔒 View Private Contacts")]
    ], resize_keyboard=True)

def edit_info_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✏️ Bio")], 
        [KeyboardButton(text="🌐 Public Contacts"), KeyboardButton(text="🔒 Private Contacts")],
        [KeyboardButton(text="🏠 Main Menu")]
    ], resize_keyboard=True)

def edit_fsm_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Cancel"), KeyboardButton(text="🗑️ Clear Field")]
    ], resize_keyboard=True)

def edit_media_fsm_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✅ Done (Save Media)")],
        [KeyboardButton(text="❌ Cancel"), KeyboardButton(text="🗑️ Clear Field")]
    ], resize_keyboard=True)

def browse_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💌 Request Contact"), KeyboardButton(text="🤝 Send Contact")],
        [KeyboardButton(text="⏩ Next Profile")],
        [KeyboardButton(text="🏠 Main Menu")]
    ], resize_keyboard=True)

def manage_action_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🌟 Set Active"), KeyboardButton(text="👁️ Toggle Vis")],
        [KeyboardButton(text="🔄 Regen ID"), KeyboardButton(text="🗑️ Delete")],
        [KeyboardButton(text="🏠 Main Menu")]
    ], resize_keyboard=True)

def profiles_menu_kb() -> ReplyKeyboardMarkup:
    """Нижняя Reply-клавиатура для меню работы со списком профилей"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Create Profile")],
        [KeyboardButton(text="🗑️ Delete All But Active")],  # Добавлена кнопка по запросу пользователя
        [KeyboardButton(text="🏠 Main Menu")]
    ], resize_keyboard=True)

# --- INLINE KEYBOARDS (Кнопки под сообщениями) ---

def profile_inline_kb(profile_uuid: str) -> InlineKeyboardMarkup:
    """Инлайн-кнопки под анкетой (решает проблему с отсутствием initData в Reply Keyboard)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏷️ Tags", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=edit&profile_id={profile_uuid}")),
            InlineKeyboardButton(text="🎛️ Filters", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=filter&profile_id={profile_uuid}"))
        ]
    ])

def skip_message_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭️ Skip Message & Send", callback_data="skip_req_msg")]])

def contact_decision_kb(req_id: str, is_sending: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if is_sending:
        buttons.append([InlineKeyboardButton(text="🤝 Share Mine Too", callback_data=f"accept_{req_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="✅ Share Contact", callback_data=f"accept_{req_id}")])
        buttons.append([InlineKeyboardButton(text="🔄 Ask For Theirs", callback_data=f"counter_{req_id}")])
    buttons.append([InlineKeyboardButton(text="❌ Hide/Decline", callback_data=f"decline_{req_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)