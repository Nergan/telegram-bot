from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from core.config import WEBHOOK_URL

# --- REPLY KEYBOARDS ---

def main_menu_kb(pool_size: int = 0) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=f"🔍 Browse ({pool_size})")],
        [KeyboardButton(text="📝 Edit Active Profile")],
        [KeyboardButton(text="👥 Profiles"), KeyboardButton(text="🏠 View Active Profile")]
    ], resize_keyboard=True)

def edit_info_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✏️ Bio"), KeyboardButton(text="📸 Edit Media")], 
        [KeyboardButton(text="📞 Manage Contacts")], 
        [KeyboardButton(text="🏠 View Active Profile")]
    ], resize_keyboard=True)

def edit_fsm_kb(show_clear: bool = True) -> ReplyKeyboardMarkup:
    buttons = [KeyboardButton(text="❌ Cancel")]
    if show_clear:
        buttons.append(KeyboardButton(text="🗑️ Clear Field"))
    return ReplyKeyboardMarkup(keyboard=[buttons], resize_keyboard=True)

def cancel_fsm_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Cancel")]
    ], resize_keyboard=True)

def browse_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⏩ Next Profile")],
        [KeyboardButton(text="🏠 View Active Profile")]
    ], resize_keyboard=True)

def manage_action_kb(is_active: bool = False) -> ReplyKeyboardMarkup:
    keyboard = []
    if not is_active:
        keyboard.append([KeyboardButton(text="🌟 Set Active")])
    keyboard.append([KeyboardButton(text="🔄 Regen ID"), KeyboardButton(text="🗑️ Delete")])
    keyboard.append([KeyboardButton(text="👥 View profiles again")])
    keyboard.append([KeyboardButton(text="🏠 View Active Profile")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def profiles_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Create Profile")],
        [KeyboardButton(text="🗑️ Delete All But Active")],
        [KeyboardButton(text="🏠 View Active Profile")]
    ], resize_keyboard=True)

# --- INLINE KEYBOARDS ---

def profile_inline_kb(profile_uuid: str, sent_count: int = 0, recv_count: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏷️ Tags", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=edit&profile_id={profile_uuid}")),
            InlineKeyboardButton(text="🎛️ Filters", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=filter&profile_id={profile_uuid}"))
        ],
        [
            InlineKeyboardButton(text=f"📥 Requests (S: {sent_count} | R: {recv_count})", web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=requests&profile_id={profile_uuid}"))
        ]
    ])

def browse_inline_kb(target_uuid: str, has_self_private: bool = True, has_target_private: bool = True, pending_actions: list = None) -> InlineKeyboardMarkup:
    if pending_actions is None:
        pending_actions = []
    buttons = []
    
    # Mutual Exchange Request Row
    if "req" in pending_actions:
        buttons.append([
            InlineKeyboardButton(text="⏳ Mutual Req Pending", callback_data="pending_alert")
        ])
    elif not has_self_private:
        buttons.append([
            InlineKeyboardButton(text="🔒 Request (Add your private info)", callback_data="no_private_alert")
        ])
    elif not has_target_private:
        buttons.append([
            InlineKeyboardButton(text="🔒 Request (They lack private info)", callback_data="target_no_private_alert")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="💌 Request", callback_data=f"req_{target_uuid}"),
            InlineKeyboardButton(text="💌 Req + Msg", callback_data=f"reqmsg_{target_uuid}")
        ])
        
    # Unilateral Send Row
    if "send" in pending_actions:
        buttons.append([
            InlineKeyboardButton(text="⏳ One-Way Pending", callback_data="pending_alert")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🤝 Send Contact", callback_data=f"send_{target_uuid}"),
            InlineKeyboardButton(text="🤝 Send + Msg", callback_data=f"sendmsg_{target_uuid}")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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

def contact_share_selection_kb(private_contacts: list, selected_ids: list, action: str) -> InlineKeyboardMarkup:
    keyboard = []
    for c in private_contacts:
        cid = c["id"]
        is_selected = cid in selected_ids
        prefix = "✅ " if is_selected else "⬜ "
        val_truncated = c["value"][:18] + "..." if len(c["value"]) > 21 else c["value"]
        
        keyboard.append([
            InlineKeyboardButton(text=f"{prefix}{val_truncated}", callback_data=f"selcon_{cid}")
        ])
        
    if action == "send":
        btn_text = "📤 Send Profile Only" if not selected_ids else "📤 Send Profile & Contacts"
    elif action == "req":
        btn_text = "📤 Send Mutual Request"
    else:
        btn_text = "📤 Confirm & Exchange"
        
    keyboard.append([InlineKeyboardButton(text=btn_text, callback_data="confirm_share_contacts")])
    keyboard.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_share_contacts")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def skip_message_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭️ Skip Message & Send", callback_data="skip_req_msg")]])

def contact_decision_kb(req_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Share Contacts", callback_data=f"accept_{req_id}")],
        [InlineKeyboardButton(text="❌ Decline", callback_data=f"decline_{req_id}")]
    ])