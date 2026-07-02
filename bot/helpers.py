from aiogram.types import InputMediaPhoto, InputMediaVideo
from bot.bot_setup import bot

def truncate(text: str, limit: int = 800) -> str:
    if not text: return ""
    return text if len(text) <= limit else text[:limit-3] + "..."

async def send_profile(chat_id: int, profile: dict, kb, is_dashboard: bool = False):
    """Universal renderer for ReplyKeyboard architecture."""
    await bot.send_chat_action(chat_id, "typing")
    
    text = f"<b>ID:</b> <code>{profile['public_uuid']}</code>\n\n"
    if is_dashboard: text = f"🏠 <b>YOUR ACTIVE PROFILE</b>\n" + text
        
    if profile.get('text'): text += f"📝 <b>Bio:</b>\n{truncate(profile['text'])}\n\n"
    if profile.get('public_contact'): text += f"🌐 <b>Public Contact:</b> {truncate(profile['public_contact'], 100)}\n\n"
    if is_dashboard and profile.get('private_contact'): 
        text += f"🔒 <b>Private Contact:</b> {truncate(profile['private_contact'], 100)}\n\n"
        
    if profile.get('tags'): text += f"🏷️ <b>Tags:</b> #{' #'.join(profile['tags'])}\n"
        
    if is_dashboard:
        filters = profile.get("filters", {})
        if any(filters.values()):
            text += "\n🎛️ <b>Active Filters:</b>\n"
            if filters.get("require_tags"): text += f"🟩 Must have: {', '.join(filters['require_tags'])}\n"
            if filters.get("exclude_tags"): text += f"🟥 Exclude: {', '.join(filters['exclude_tags'])}\n"
            if filters.get("any_tags"): text += f"🟦 Any of: {', '.join(filters['any_tags'])}\n"
            
    media = profile.get("media", {})
    items = media.get("items", []) if isinstance(media, dict) else []
    voice = media.get("voice") if isinstance(media, dict) else None

    # Note: Telegram API doesn't allow ReplyKeyboardMarkup directly on MediaGroups.
    # Therefore, we send media first, then send the text/controls.
    if items:
        await bot.send_chat_action(chat_id, "upload_photo")
        if len(items) == 1:
            itm = items[0]
            if itm['type'] == 'photo': await bot.send_photo(chat_id, itm['file_id'])
            elif itm['type'] == 'video': await bot.send_video(chat_id, itm['file_id'])
        else:
            media_group = []
            for i, itm in enumerate(items[:5]):
                if itm['type'] == 'photo': media_group.append(InputMediaPhoto(media=itm['file_id']))
                elif itm['type'] == 'video': media_group.append(InputMediaVideo(media=itm['file_id']))
            await bot.send_media_group(chat_id, media=media_group)

    if voice:
        await bot.send_voice(chat_id, voice)

    await bot.send_message(chat_id, text, reply_markup=kb)