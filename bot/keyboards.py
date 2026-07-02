from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from core.config import WEBHOOK_URL

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚙️ Edit Tags", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=edit")),
            InlineKeyboardButton(text="🔍 Browse (Filter)", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=filter"))
        ],
        [InlineKeyboardButton(text="👤 My Profile", callback_data="my_profile")]
    ])

def profile_card_kb(target_uuid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💌 Request Contact", callback_data=f"req_{target_uuid}"),
            InlineKeyboardButton(text="🤝 Send My Contact", callback_data=f"send_{target_uuid}")
        ],
        [InlineKeyboardButton(text="⏩ Next Profile", callback_data="next_profile")]
    ])

def skip_message_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Skip Message & Send", callback_data="skip_req_msg")]
    ])

def contact_decision_kb(req_id: str, is_sending: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if is_sending:
        buttons.append([InlineKeyboardButton(text="🤝 Share Mine Too", callback_data=f"accept_{req_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="✅ Share Contact", callback_data=f"accept_{req_id}")])
        buttons.append([InlineKeyboardButton(text="🔄 Ask For Theirs First", callback_data=f"counter_{req_id}")])
    
    buttons.append([InlineKeyboardButton(text="❌ Hide/Decline", callback_data=f"decline_{req_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)