import html
import logging
from aiogram.types import LinkPreviewOptions, InputMediaPhoto, InputMediaVideo
from bot.bot_setup import bot

logger = logging.getLogger(__name__)

def truncate(text: str, limit: int = 4000) -> str:
    if not text: return ""
    return text if len(text) <= limit else text[:limit-3] + "..."

async def send_profile(chat_id: int, profile: dict, kb, custom_prefix: str = ""):
    """Intelligently groups Text + Media to respect Telegram API limits while attaching keyboards natively."""
    await bot.send_chat_action(chat_id, "typing")
    
    text = f"{custom_prefix}<b>ID:</b> <code>{profile['public_uuid']}</code>\n\n"
        
    if profile.get('text'): text += f"📝 <b>Bio:</b>\n{html.escape(profile['text'])}\n\n"
    if profile.get('public_contact'): text += f"🌐 <b>Public Contacts:</b>\n{html.escape(profile['public_contact'])}\n\n"
    if profile.get('tags'): text += f"🏷️ <b>Tags:</b> #{' #'.join(profile['tags'])}\n"
            
    media = profile.get("media", [])
    opts = LinkPreviewOptions(is_disabled=True)

    try:
        if not media:
            # 0 Media: Send text directly with keyboard
            final_text = truncate(text, 4000)
            await bot.send_message(chat_id, final_text, reply_markup=kb, link_preview_options=opts)
            
        elif len(media) == 1:
            # 1 Media: Send media with text as caption and keyboard attached
            final_text = truncate(text, 1024)
            m = media[0]
            if m['type'] == 'photo': await bot.send_photo(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'video': await bot.send_video(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'animation': await bot.send_animation(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'audio': await bot.send_audio(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'document': await bot.send_document(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'voice': await bot.send_voice(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            
        else:
            # 2+ Media: Telegram forbids keyboards on MediaGroups. 
            # We send the album first (no caption), then a standard text message with the keyboard.
            final_text = truncate(text, 4000)
            media_group = []
            for m in media[:10]:
                if m['type'] == 'photo': media_group.append(InputMediaPhoto(media=m['file_id']))
                elif m['type'] == 'video': media_group.append(InputMediaVideo(media=m['file_id']))
            
            await bot.send_media_group(chat_id, media=media_group)
            await bot.send_message(chat_id, final_text, reply_markup=kb, link_preview_options=opts)
            
    except Exception as e:
        logger.error(f"Failed to render profile {profile['public_uuid']}: {e}")
        final_text = truncate(text, 4000)
        await bot.send_message(chat_id, f"⚠️ <i>Some media attachments could not be loaded.</i>\n\n{final_text}", reply_markup=kb, link_preview_options=opts)