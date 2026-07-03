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
        [KeyboardButton(text="📞 Manage Contacts")], 
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
    """Убрана кнопка💣 Delete All Profiles"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Create Profile")],
        [KeyboardButton(text="🗑️ Delete All But Active")],
        [KeyboardButton(text="🏠 View Active Profile")]
    ], resize_keyboard=True)

# --- INLINE KEYBOARDS ---

def profile_inline_kb(profile_uuid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏷️ Tags", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=edit&profile_id={profile_uuid}")),
            InlineKeyboardButton(text="🎛️ Filters", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=filter&profile_id={profile_uuid}"))
        ]
    ])

def browse_inline_kb(target_uuid: str, has_private: bool = True) -> InlineKeyboardMarkup:
    if not has_private:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 Add Private Contact to Interact", callback_data="no_private_alert")]
        ])
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

def manage_contacts_inline_kb(contacts: list) -> InlineKeyboardMarkup:
    keyboard = []
    for c in contacts:
        cid = c["id"]
        val_truncated = c["value"][:12] + "..." if len(c["value"]) > 15 else c["value"]
        
        vis_text = "🌐 Make Public" if not c.get("is_public") else "🔒 Make Private"
        row = [InlineKeyboardButton(text=f"{vis_text} ({val_truncated})", callback_data=f"togglecon_{cid}")]
        
        if cid != "tg_username":
            row.append(InlineKeyboardButton(text="🗑️ Del", callback_data=f"delcon_{cid}"))
            
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton(text="➕ Add New Contact", callback_data="add_contact_fsm")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def contact_share_selection_kb(private_contacts: list, selected_ids: list) -> InlineKeyboardMarkup:
    keyboard = []
    for c in private_contacts:
        cid = c["id"]
        is_selected = cid in selected_ids
        prefix = "✅ " if is_selected else "⬜ "
        val_truncated = c["value"][:18] + "..." if len(c["value"]) > 21 else c["value"]
        
        keyboard.append([
            InlineKeyboardButton(text=f"{prefix}{val_truncated}", callback_data=f"selcon_{cid}")
        ])
        
    keyboard.append([InlineKeyboardButton(text="📤 Confirm & Share", callback_data="confirm_share_contacts")])
    keyboard.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_share_contacts")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def skip_message_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭️ Skip Message & Send", callback_data="skip_req_msg")]])

def contact_decision_kb(req_id: str, is_sending: bool = False, can_counter: bool = True) -> InlineKeyboardMarkup:
    buttons = []
    if is_sending:
        buttons.append([InlineKeyboardButton(text="🤝 Share Mine Too", callback_data=f"accept_{req_id}")])
    else:
        row = [InlineKeyboardButton(text="✅ Share Contact", callback_data=f"accept_{req_id}")]
        if can_counter:
            row.append(InlineKeyboardButton(text="🔄 Ask For Theirs", callback_data=f"counter_{req_id}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="❌ Hide/Decline", callback_data=f"decline_{req_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)