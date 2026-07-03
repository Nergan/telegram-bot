import html
from aiogram.types import LinkPreviewOptions, InputMediaPhoto, InputMediaVideo
from bot.bot_setup import bot

def truncate(text: str, limit: int = 4000) -> str:
    if not text: return ""
    return text if len(text) <= limit else text[:limit-3] + "..."

async def send_profile(chat_id: int, profile: dict, kb):
    """Отображает анкету в публичном виде без посторонних плашек."""
    await bot.send_chat_action(chat_id, "typing")
    
    # Больше нет префикса "YOUR ACTIVE PROFILE" — анкета выглядит одинаково для всех
    text = f"<b>ID:</b> <code>{profile['public_uuid']}</code>\n\n"
        
    if profile.get('text'): text += f"📝 <b>Bio:</b>\n{html.escape(profile['text'])}\n\n"
    if profile.get('public_contact'): text += f"🌐 <b>Public Contacts:</b>\n{html.escape(profile['public_contact'])}\n\n"
    if profile.get('tags'): text += f"🏷️ <b>Tags:</b> #{' #'.join(profile['tags'])}\n"
            
    media = profile.get("media", [])
    opts = LinkPreviewOptions(is_disabled=True)
    final_text = truncate(text, 1024 if media else 4000)

    try:
        if not media:
            await bot.send_message(chat_id, final_text, reply_markup=kb, link_preview_options=opts)
        elif len(media) == 1:
            m = media[0]
            if m['type'] == 'photo': await bot.send_photo(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'video': await bot.send_video(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'animation': await bot.send_animation(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'audio': await bot.send_audio(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'document': await bot.send_document(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'voice': await bot.send_voice(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
        else:
            media_group = []
            for i, m in enumerate(media[:10]):
                cap = final_text if i == 0 else None
                if m['type'] == 'photo': media_group.append(InputMediaPhoto(media=m['file_id'], caption=cap))
                elif m['type'] == 'video': media_group.append(InputMediaVideo(media=m['file_id'], caption=cap))
            
            await bot.send_media_group(chat_id, media=media_group)
            # Изменено: заменено "👇 Menu:" на более эстетичное и аккуратное "⚙️ Options:"
            await bot.send_message(chat_id, "⚙️ Options:", reply_markup=kb)
            
    except Exception as e:
        # Diagnostic printing ensures the user knows WHY Telegram rejected the API call.
        await bot.send_message(chat_id, f"⚠️ <i>Media rendering failed: {str(e)}</i>\n\n{final_text}", reply_markup=kb, link_preview_options=opts)