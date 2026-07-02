import html
from aiogram.types import LinkPreviewOptions
from bot.bot_setup import bot

def truncate(text: str, limit: int = 4000) -> str:
    if not text: return ""
    return text if len(text) <= limit else text[:limit-3] + "..."

async def send_profile(chat_id: int, profile: dict, kb, is_main_menu: bool = False):
    """Combines text and exactly 1 media into a single message."""
    await bot.send_chat_action(chat_id, "typing")
    
    text = f"<b>ID:</b> <code>{profile['public_uuid']}</code>\n\n"
    if is_main_menu: text = f"🏠 <b>YOUR ACTIVE PROFILE</b>\n" + text
        
    if profile.get('text'): 
        text += f"📝 <b>Bio:</b>\n{html.escape(profile['text'])}\n\n"
        
    if profile.get('public_contact'): 
        text += f"🌐 <b>Public Contacts:</b>\n{html.escape(profile['public_contact'])}\n\n"
        
    if is_main_menu and profile.get('private_contact'): 
        text += f"🔒 <b>Private Contacts:</b>\n{html.escape(profile['private_contact'])}\n\n"
        
    if profile.get('tags'): 
        text += f"🏷️ <b>Tags:</b> #{' #'.join(profile['tags'])}\n"
        
    if is_main_menu:
        filters = profile.get("filters", {})
        if any(filters.values()):
            text += "\n🎛️ <b>Active Filters:</b>\n"
            if filters.get("require_tags"): text += f"🟩 Must have: {', '.join(filters['require_tags'])}\n"
            if filters.get("exclude_tags"): text += f"🟥 Exclude: {', '.join(filters['exclude_tags'])}\n"
            if filters.get("any_tags"): text += f"🟦 Any of: {', '.join(filters['any_tags'])}\n"
            
    media = profile.get("media")
    opts = LinkPreviewOptions(is_disabled=True)
    
    # Telegram max caption length is 1024. Text limits: 4096.
    final_text = truncate(text, 1024 if media else 4000)

    try:
        if not media:
            await bot.send_message(chat_id, final_text, reply_markup=kb, link_preview_options=opts)
        else:
            m_type = media.get('type')
            f_id = media.get('file_id')
            
            if m_type == 'photo': await bot.send_photo(chat_id, f_id, caption=final_text, reply_markup=kb)
            elif m_type == 'video': await bot.send_video(chat_id, f_id, caption=final_text, reply_markup=kb)
            elif m_type == 'voice': await bot.send_voice(chat_id, f_id, caption=final_text, reply_markup=kb)
            elif m_type == 'animation': await bot.send_animation(chat_id, f_id, caption=final_text, reply_markup=kb)
            elif m_type == 'audio': await bot.send_audio(chat_id, f_id, caption=final_text, reply_markup=kb)
            elif m_type == 'document': await bot.send_document(chat_id, f_id, caption=final_text, reply_markup=kb)
            else:
                await bot.send_message(chat_id, final_text, reply_markup=kb, link_preview_options=opts)
    except Exception:
        # Fallback if media ID is invalid or deleted from Telegram servers
        await bot.send_message(chat_id, f"⚠️ <i>Media attachment is no longer available.</i>\n\n{final_text}", reply_markup=kb, link_preview_options=opts)