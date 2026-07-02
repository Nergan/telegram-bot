from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from core.config import WEBHOOK_URL

def dashboard_kb(profile_uuid: str) -> InlineKeyboardMarkup:
    """The central navigation hub attached to the active profile."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Start Browsing", callback_data="browse_profiles")],
        [
            InlineKeyboardButton(text="⚙️ Filter Settings", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=filter&profile_id={profile_uuid}")),
            InlineKeyboardButton(text="🏷️ My Tags", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=edit&profile_id={profile_uuid}"))
        ],
        [
            InlineKeyboardButton(text="✏️ Edit Info/Media", callback_data=f"edit_menu_{profile_uuid}"),
            InlineKeyboardButton(text="👥 Manage Profiles", callback_data="my_profiles")
        ]
    ])

def profile_editor_kb(profile_uuid: str) -> InlineKeyboardMarkup:
    """FSM Menu for editing specific fields."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Edit Bio", callback_data=f"edit_field_bio_{profile_uuid}")],
        [InlineKeyboardButton(text="📸 Edit Media", callback_data=f"edit_field_media_{profile_uuid}")],
        [
            InlineKeyboardButton(text="🌐 Edit Public Contact", callback_data=f"edit_field_pub_{profile_uuid}"),
            InlineKeyboardButton(text="🔒 Edit Private Contact", callback_data=f"edit_field_priv_{profile_uuid}")
        ],
        [InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="dashboard")]
    ])

def profiles_list_kb(profiles: list) -> InlineKeyboardMarkup:
    buttons = []
    for p in profiles:
        status = "🌟 Active" if p.get("is_active") else "Inactive"
        if p.get("is_hidden"): status += " (Hidden)"
        buttons.append([InlineKeyboardButton(text=f"ID: {p['public_uuid']} [{status}]", callback_data=f"manage_prof_{p['public_uuid']}")])
        
    buttons.append([InlineKeyboardButton(text="➕ Create Profile", callback_data="create_profile")])
    buttons.append([InlineKeyboardButton(text="◀️ Back to Dashboard", callback_data="dashboard")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def profile_management_kb(profile: dict) -> InlineKeyboardMarkup:
    uuid = profile['public_uuid']
    buttons = []
    if not profile.get('is_active'):
        buttons.append([InlineKeyboardButton(text="🌟 Set as Active", callback_data=f"set_active_{uuid}")])

    hide_text = "👁️ Unhide Profile" if profile.get('is_hidden') else "🙈 Hide Profile"
    buttons.append([
        InlineKeyboardButton(text=hide_text, callback_data=f"toggle_hide_{uuid}"),
        InlineKeyboardButton(text="🔄 Regen ID", callback_data=f"regen_id_{uuid}")
    ])
    buttons.append([InlineKeyboardButton(text="🗑️ Delete", callback_data=f"delete_prof_{uuid}")])
    buttons.append([InlineKeyboardButton(text="◀️ Back to List", callback_data="my_profiles")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def profile_card_kb(target_uuid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💌 Request Contact", callback_data=f"req_{target_uuid}"),
            InlineKeyboardButton(text="🤝 Send My Contact", callback_data=f"send_{target_uuid}")
        ],
        [InlineKeyboardButton(text="⏩ Next Profile", callback_data="next_profile")],
        [InlineKeyboardButton(text="🏠 Dashboard", callback_data="dashboard")]
    ])