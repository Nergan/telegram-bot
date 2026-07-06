import html
import logging
from aiogram.types import LinkPreviewOptions, InputMediaPhoto, InputMediaVideo
from bot.bot_setup import bot
from infrastructure.locales import _
from application.services import TagService

logger = logging.getLogger(__name__)

def truncate(text: str, limit: int = 4000) -> str:
    if not text: return ""
    return text if len(text) <= limit else text[:limit-3] + "..."

async def send_profile(chat_id: int, profile: dict, kb, lang: str, tag_service: TagService, custom_prefix: str = ""):
    await bot.send_chat_action(chat_id, "typing")
    text = custom_prefix + _("lbl_id", lang, profile['public_uuid'])
        
    if profile.get('text'): text += _("lbl_bio", lang, html.escape(profile['text']))
    
    contacts = profile.get("contacts", [])
    public_contacts = [c for c in contacts if c.get("is_public")]
    if public_contacts:
        text += _("lbl_pub_con", lang)
        for c in public_contacts:
            text += f"• {html.escape(c['value'])}\n"
        text += "\n"
        
    if profile.get('tags'): 
        tag_docs = await tag_service.get_tags_by_ids(profile['tags'])
        translated_tags = []
        for tid in profile['tags']:
            tag_def = next((t for t in tag_docs if t['_id'] == tid), None)
            if tag_def:
                display = tag_def.get('display', {})
                # Safely fallback to raw ID if the locale is inexplicably missing
                translated_tags.append(display.get(lang, display.get('en', str(tid))))
            else:
                translated_tags.append(str(tid))
        
        if translated_tags:
            text += _("lbl_tags", lang, ' • '.join(translated_tags))
            
    media = profile.get("media", [])
    opts = LinkPreviewOptions(is_disabled=True)

    try:
        if not media:
            final_text = truncate(text, 4000)
            await bot.send_message(chat_id, final_text, reply_markup=kb, link_preview_options=opts)
        elif len(media) == 1:
            final_text = truncate(text, 1024)
            m = media[0]
            if m['type'] == 'photo': await bot.send_photo(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'video': await bot.send_video(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'animation': await bot.send_animation(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'audio': await bot.send_audio(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'document': await bot.send_document(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
            elif m['type'] == 'voice': await bot.send_voice(chat_id, m['file_id'], caption=final_text, reply_markup=kb)
        else:
            final_text = truncate(text, 1024)
            media_group = []
            for i, m in enumerate(media[:10]):
                cap = final_text if i == 0 else None
                if m['type'] == 'photo': media_group.append(InputMediaPhoto(media=m['file_id'], caption=cap))
                elif m['type'] == 'video': media_group.append(InputMediaVideo(media=m['file_id'], caption=cap))
            await bot.send_media_group(chat_id, media=media_group)
            await bot.send_message(chat_id, _("lbl_options", lang), reply_markup=kb)
    except Exception as e:
        logger.error(f"Failed to render profile {profile['public_uuid']}: {e}")
        final_text = truncate(text, 4000)
        await bot.send_message(chat_id, _("lbl_err_media", lang, final_text), reply_markup=kb, link_preview_options=opts)