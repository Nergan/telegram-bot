from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from infrastructure.config import WEBHOOK_URL
from infrastructure.locales import _

def main_menu_kb(lang: str, pool_size: int = 0, has_active: bool = True) -> ReplyKeyboardMarkup:
    if not has_active:
        return ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text=_("btn_profiles", lang))]
        ], resize_keyboard=True)
        
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=_("btn_browse", lang, pool_size))],
        [KeyboardButton(text=_("btn_edit_active", lang))],
        [KeyboardButton(text=_("btn_profiles", lang)), KeyboardButton(text=_("btn_view_active", lang))]
    ], resize_keyboard=True)

def edit_info_menu_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=_("btn_bio", lang)), KeyboardButton(text=_("btn_media", lang))], 
        [KeyboardButton(text=_("btn_contacts", lang))], 
        [KeyboardButton(text=_("btn_view_active", lang))]
    ], resize_keyboard=True)

def edit_fsm_kb(lang: str, show_clear: bool = True) -> ReplyKeyboardMarkup:
    buttons = [KeyboardButton(text=_("btn_cancel", lang))]
    if show_clear:
        buttons.append(KeyboardButton(text=_("btn_clear", lang)))
    return ReplyKeyboardMarkup(keyboard=[buttons], resize_keyboard=True)

def cancel_fsm_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=_("btn_cancel", lang))]], resize_keyboard=True)

def browse_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=_("btn_next", lang))],
        [KeyboardButton(text=_("btn_view_active", lang))]
    ], resize_keyboard=True)

def manage_action_kb(lang: str, is_active: bool = False) -> ReplyKeyboardMarkup:
    keyboard = []
    if not is_active:
        keyboard.append([KeyboardButton(text=_("btn_set_active", lang))])
    else:
        keyboard.append([KeyboardButton(text=_("btn_deactivate", lang))])
        
    keyboard.append([KeyboardButton(text=_("btn_regen_id", lang)), KeyboardButton(text=_("btn_delete", lang))])
    keyboard.append([KeyboardButton(text=_("btn_view_again", lang))])
    keyboard.append([KeyboardButton(text=_("btn_view_active", lang))])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def profiles_menu_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=_("btn_create", lang))],
        [KeyboardButton(text=_("btn_del_all", lang))],
        [KeyboardButton(text=_("btn_view_active", lang))]
    ], resize_keyboard=True)

def profile_inline_kb(lang: str, profile_uuid: str, sent_count: int = 0, recv_count: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("btn_tags", lang), web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=edit&profile_id={profile_uuid}&lang={lang}")),
            InlineKeyboardButton(text=_("btn_filters", lang), web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=filter&profile_id={profile_uuid}&lang={lang}"))
        ],
        [
            InlineKeyboardButton(text=_("btn_requests", lang, sent_count, recv_count), web_app=WebAppInfo(url=f"{WEBHOOK_URL}/webapp?mode=requests&profile_id={profile_uuid}&lang={lang}"))
        ]
    ])

def browse_inline_kb(lang: str, target_uuid: str, has_self_private: bool = True, has_target_private: bool = True, pending_actions: list = None) -> InlineKeyboardMarkup:
    if pending_actions is None: pending_actions = []
    buttons = []
    if "req" in pending_actions:
        buttons.append([InlineKeyboardButton(text="⏳", callback_data="pending_alert")])
    elif not has_self_private:
        buttons.append([InlineKeyboardButton(text="🔒 (+)", callback_data="no_private_alert")])
    elif not has_target_private:
        buttons.append([InlineKeyboardButton(text="🔒 (-)", callback_data="target_no_private_alert")])
    else:
        buttons.append([
            InlineKeyboardButton(text="💌", callback_data=f"req_{target_uuid}"),
            InlineKeyboardButton(text="💌 + Msg", callback_data=f"reqmsg_{target_uuid}")
        ])
    if "send" in pending_actions:
        buttons.append([InlineKeyboardButton(text="⏳", callback_data="pending_alert")])
    else:
        buttons.append([
            InlineKeyboardButton(text="🤝", callback_data=f"send_{target_uuid}"),
            InlineKeyboardButton(text="🤝 + Msg", callback_data=f"sendmsg_{target_uuid}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def manage_contacts_inline_kb(lang: str, contacts: list) -> InlineKeyboardMarkup:
    keyboard = []
    for c in contacts:
        cid = c["id"]
        val_truncated = c["value"][:12] + "..." if len(c["value"]) > 15 else c["value"]
        vis_text = "🌐" if not c.get("is_public") else "🔒"
        row = [InlineKeyboardButton(text=f"{vis_text} ({val_truncated})", callback_data=f"togglecon_{cid}")]
        if cid != "tg_username":
            row.append(InlineKeyboardButton(text="🗑️", callback_data=f"delcon_{cid}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="➕", callback_data="add_contact_fsm")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def contact_share_selection_kb(lang: str, private_contacts: list, selected_ids: list, action: str) -> InlineKeyboardMarkup:
    keyboard = []
    for c in private_contacts:
        cid = c["id"]
        prefix = "✅ " if cid in selected_ids else "⬜ "
        val_truncated = c["value"][:18] + "..." if len(c["value"]) > 21 else c["value"]
        keyboard.append([InlineKeyboardButton(text=f"{prefix}{val_truncated}", callback_data=f"selcon_{cid}")])
    btn_text = "📤 Confirm"
    keyboard.append([InlineKeyboardButton(text=btn_text, callback_data="confirm_share_contacts")])
    keyboard.append([InlineKeyboardButton(text=_("btn_cancel", lang), callback_data="cancel_share_contacts")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def skip_message_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭️", callback_data="skip_req_msg")]])

def contact_decision_kb(lang: str, req_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅", callback_data=f"accept_{req_id}")],
        [InlineKeyboardButton(text="❌", callback_data=f"decline_{req_id}")]
    ])