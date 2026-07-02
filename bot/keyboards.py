from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from core.config import WEBHOOK_URL

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚙️ Edit Tags", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=edit")),
            InlineKeyboardButton(text="🔍 Browse (Filter)", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=filter"))
        ],
        # Изменено на "my_profiles" (во множественном числе) для соответствия handlers.py
        [InlineKeyboardButton(text="👤 My Profiles", callback_data="my_profiles")]
    ])

def profiles_list_kb(profiles: list) -> InlineKeyboardMarkup:
    """Генерирует список профилей пользователя"""
    buttons = []
    for p in profiles:
        status = "🌟 Active" if p.get("is_active") else "Inactive"
        if p.get("is_hidden"):
            status += " (Hidden)"
            
        buttons.append([
            InlineKeyboardButton(
                text=f"ID: {p['public_uuid']} [{status}]",
                callback_data=f"manage_prof_{p['public_uuid']}"
            )
        ])
        
    buttons.append([InlineKeyboardButton(text="➕ Create Profile", callback_data="create_profile")])
    buttons.append([InlineKeyboardButton(text="◀️ Back to Main Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def profile_management_kb(profile: dict) -> InlineKeyboardMarkup:
    """Панель управления конкретным профилем"""
    uuid = profile['public_uuid']
    buttons = []

    # Передаем конкретный profile_id в Web App для редактирования тегов этой анкеты
    buttons.append([
        InlineKeyboardButton(
            text="🏷️ Edit Tags (Web App)",
            web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=edit&profile_id={uuid}")
        )
    ])

    # Кнопка активации (показывается только для неактивных профилей)
    if not profile.get('is_active'):
        buttons.append([InlineKeyboardButton(text="🌟 Set as Active", callback_data=f"set_active_{uuid}")])

    # Кнопка видимости анкеты
    hide_text = "👁️ Unhide Profile" if profile.get('is_hidden') else "🙈 Hide Profile"
    buttons.append([InlineKeyboardButton(text=hide_text, callback_data=f"toggle_hide_{uuid}")])

    # Кнопки регенерации ID и удаления в одну строку
    buttons.append([
        InlineKeyboardButton(text="🔄 Regen ID", callback_data=f"regen_id_{uuid}"),
        InlineKeyboardButton(text="🗑️ Delete", callback_data=f"delete_prof_{uuid}")
    ])

    buttons.append([InlineKeyboardButton(text="◀️ Back to My Profiles", callback_data="my_profiles")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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