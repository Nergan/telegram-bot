import uuid
import logging
import asyncio
import datetime
from collections import deque
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.states import ProfileSetup
from bot.keyboards import edit_info_menu_kb, edit_fsm_kb, profiles_menu_kb, manage_action_kb, profile_inline_kb
from bot.helpers import send_profile
from infrastructure.locales import _, _btn
from application.services import ProfileService, ContactRequestService, TagService

router = Router()
logger = logging.getLogger(__name__)

ALBUM_BUFFER_MEM = {}
PROCESSED_ALBUMS_MEM = deque(maxlen=100)

@router.message(F.text.in_(_btn("btn_edit_active")))
async def edit_info_menu(message: types.Message, lang: str, profile_service: ProfileService):
    active_prof = await profile_service.get_active_profile(message.from_user.id)
    if not active_prof: return await message.answer(_("prof_not_found", lang))
    await message.answer(_("menu_edit", lang), reply_markup=edit_info_menu_kb(lang))

@router.message(F.text.in_(_btn("btn_bio")))
async def init_edit_bio(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService):
    active_prof = await profile_service.get_active_profile(message.from_user.id)
    if not active_prof: return await message.answer(_("prof_not_found", lang))
    
    await state.set_state(ProfileSetup.waiting_for_bio)
    has_bio = bool(active_prof.get("text"))
    await message.answer(_("send_bio", lang), reply_markup=edit_fsm_kb(lang, show_clear=has_bio))

@router.message(F.text.in_(_btn("btn_media")))
async def init_edit_media(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService):
    active_prof = await profile_service.get_active_profile(message.from_user.id)
    if not active_prof: return await message.answer(_("prof_not_found", lang))
    
    await state.set_state(ProfileSetup.waiting_for_media)
    has_media = bool(active_prof.get("media"))
    await message.answer(_("send_media", lang), reply_markup=edit_fsm_kb(lang, show_clear=has_media))

@router.message(ProfileSetup.waiting_for_bio, ~F.text.startswith("/"))
async def capture_text(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService):
    if message.text and message.text in _btn("btn_cancel"):
        from bot.handlers.base import fsm_cancel
        await fsm_cancel(message, state, lang, profile_service)
        return
    if message.text and message.text in _btn("btn_clear"):
        from bot.handlers.base import fsm_clear
        await fsm_clear(message, state, lang, profile_service)
        return
    if message.content_type != 'text': 
        return await message.answer(_("invalid_text", lang))
    
    active_prof = await profile_service.get_active_profile(message.from_user.id)
    if not active_prof: return await message.answer(_("prof_not_found", lang))
    
    await profile_service.update_profile(active_prof['public_uuid'], {"text": message.text})
    await message.answer(_("bio_saved", lang), reply_markup=edit_info_menu_kb(lang))
    await state.clear()

@router.message(ProfileSetup.waiting_for_media, ~F.text.startswith("/"))
async def capture_media(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService, mongo_db=None):
    if message.text and message.text in _btn("btn_cancel"):
        from bot.handlers.base import fsm_cancel
        await fsm_cancel(message, state, lang, profile_service)
        return
    if message.text and message.text in _btn("btn_clear"):
        from bot.handlers.base import fsm_clear
        await fsm_clear(message, state, lang, profile_service)
        return
        
    valid_types = ['photo', 'video', 'voice', 'animation', 'audio', 'document']
    if message.content_type not in valid_types:
        return await message.answer(_("invalid_media", lang))
        
    active_prof = await profile_service.get_active_profile(message.from_user.id)
    if not active_prof: return await message.answer(_("prof_not_found", lang))

    media_doc = {"type": message.content_type}
    if message.photo: media_doc['file_id'] = message.photo[-1].file_id
    elif message.video: media_doc['file_id'] = message.video.file_id
    elif message.voice: media_doc['file_id'] = message.voice.file_id
    elif message.animation: media_doc['file_id'] = message.animation.file_id
    elif message.audio: media_doc['file_id'] = message.audio.file_id
    elif message.document: media_doc['file_id'] = message.document.file_id
    
    if message.media_group_id:
        if mongo_db:
            processed = await mongo_db.db.processed_albums.find_one({"media_group_id": message.media_group_id})
            if processed:
                return
                
            res = await mongo_db.db.album_buffers.find_one_and_update(
                {"media_group_id": message.media_group_id},
                {"$push": {"media": media_doc}},
                upsert=True,
                return_document=True
            )
            
            if len(res.get("media", [])) == 1:
                try:
                    await message.answer(_("album_proc", lang))
                    await asyncio.sleep(1.5)
                    final_doc = await mongo_db.db.album_buffers.find_one_and_delete({"media_group_id": message.media_group_id})
                    if final_doc and final_doc.get("media"):
                        await profile_service.update_profile(active_prof['public_uuid'], {"media": final_doc["media"]})
                        await mongo_db.db.processed_albums.insert_one({
                            "media_group_id": message.media_group_id,
                            "created_at": datetime.datetime.now(datetime.timezone.utc)
                        })
                        await state.clear()
                        await message.answer(_("album_saved", lang), reply_markup=edit_info_menu_kb(lang))
                except Exception as e:
                    await mongo_db.db.album_buffers.delete_one({"media_group_id": message.media_group_id})
                    logger.error(f"Distributed album processing error: {e}")
        else:
            global ALBUM_BUFFER_MEM, PROCESSED_ALBUMS_MEM
            if message.media_group_id in PROCESSED_ALBUMS_MEM:
                return
                
            if message.media_group_id not in ALBUM_BUFFER_MEM:
                ALBUM_BUFFER_MEM[message.media_group_id] = [media_doc]
                try:
                    await message.answer(_("album_proc", lang))
                    await asyncio.sleep(1.5)
                    buffered_docs = ALBUM_BUFFER_MEM.pop(message.media_group_id, [])
                    if buffered_docs:
                        await profile_service.update_profile(active_prof['public_uuid'], {"media": buffered_docs})
                        PROCESSED_ALBUMS_MEM.append(message.media_group_id)
                        await state.clear()
                        await message.answer(_("album_saved", lang), reply_markup=edit_info_menu_kb(lang))
                except Exception as e:
                    ALBUM_BUFFER_MEM.pop(message.media_group_id, None)
                    logger.error(f"Album processing error: {e}")
            else:
                ALBUM_BUFFER_MEM[message.media_group_id].append(media_doc)
    else:
        await profile_service.update_profile(active_prof['public_uuid'], {"media": [media_doc]})
        await message.answer(_("media_saved", lang), reply_markup=edit_info_menu_kb(lang))
        await state.clear()

@router.message(F.text.in_(_btn("btn_profiles")))
async def profiles_menu(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService):
    if state: await state.clear()
    profiles = await profile_service.get_all_by_user(message.from_user.id)
    count = len(profiles)
    
    inline_kb = []
    for p in profiles:
        status = "🌟 Active" if p.get("is_active") else "⚪ Inactive"
        bio = p.get("text", "") or ""
        bio_clean = bio.strip().replace("\n", " ")
        bio_snippet = bio_clean[:12] + "..." if len(bio_clean) > 12 else bio_clean
        label = f"📝 {bio_snippet} | ID: {p['public_uuid']} [{status}]" if bio_snippet else f"ID: {p['public_uuid']} [{status}]"
        inline_kb.append([InlineKeyboardButton(text=label, callback_data=f"manage_prof_{p['public_uuid']}")])
        
    await message.answer(_("btn_profiles", lang), reply_markup=profiles_menu_kb(lang))
    if inline_kb:
        await message.answer(_("profiles_header", lang, count), reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb))

@router.message(F.text.in_(_btn("btn_create")))
async def create_profile_cmd(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService):
    prof = await profile_service.create_profile(message.from_user.id, message.from_user.username)
    if not prof: return await message.answer(_("prof_limit", lang))
    await message.answer(_("prof_created", lang))
    await profiles_menu(message, state, lang, profile_service)

@router.message(F.text.in_(_btn("btn_del_all")))
async def del_all_but_active(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService):
    await profile_service.delete_all_but_active(message.from_user.id)
    await message.answer(_("prof_del_inactive", lang))
    await profiles_menu(message, state, lang, profile_service)

@router.callback_query(F.data.startswith("manage_prof_"))
async def manage_prof_cb(
    callback: types.CallbackQuery, state: FSMContext, lang: str, 
    profile_service: ProfileService, contact_req_service: ContactRequestService, tag_service: TagService
):
    await state.clear()
    prof_uuid = callback.data.split("_")[2]
    profile = await profile_service.get_profile_by_uuid(prof_uuid)
    if not profile or profile['user_id'] != callback.from_user.id:
        return await callback.answer(_("prof_not_found", lang), show_alert=True)
    
    await state.update_data(managing_uuid=prof_uuid)
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    is_active = profile.get('is_active', False)
    await callback.message.answer(_("prof_managing", lang), reply_markup=manage_action_kb(lang, is_active))
    
    sent_c, recv_c = await contact_req_service.get_requests_counts(callback.from_user.id)
    await send_profile(callback.from_user.id, profile, profile_inline_kb(lang, prof_uuid, sent_c, recv_c), lang, tag_service)
    await callback.answer()

@router.message(F.text.in_(_btn("btn_set_active")) | F.text.in_(_btn("btn_deactivate")) | F.text.in_(_btn("btn_regen_id")) | F.text.in_(_btn("btn_delete")) | F.text.in_(_btn("btn_view_again")))
async def manage_actions(
    message: types.Message, state: FSMContext, lang: str, 
    profile_service: ProfileService, contact_req_service: ContactRequestService, tag_service: TagService
):
    data = await state.get_data()
    prof_uuid = data.get("managing_uuid")
    if not prof_uuid or message.text == _("btn_view_again", lang): 
        return await profiles_menu(message, state, lang, profile_service)
    
    user_id = message.from_user.id
    p = await profile_service.get_profile_by_uuid(prof_uuid)
    if not p: return await profiles_menu(message, state, lang, profile_service)

    if message.text == _("btn_set_active", lang):
        await profile_service.set_active_profile(user_id, prof_uuid)
        await message.answer(_("prof_activated", lang))
        from bot.handlers.base import show_main_menu
        await show_main_menu(message, state, lang, profile_service, contact_req_service, tag_service)
    elif message.text == _("btn_deactivate", lang):
        await profile_service.deactivate_profile(user_id, prof_uuid)
        await message.answer(_("prof_deactivated", lang))
        from bot.handlers.base import show_main_menu
        await show_main_menu(message, state, lang, profile_service, contact_req_service, tag_service)
    elif message.text == _("btn_regen_id", lang):
        new_uuid = uuid.uuid4().hex[:8]
        await profile_service.update_profile(prof_uuid, {"public_uuid": new_uuid})
        await state.update_data(managing_uuid=new_uuid)
        p = await profile_service.get_profile_by_uuid(new_uuid)
        
        await message.answer(_("prof_regen", lang), reply_markup=manage_action_kb(lang, p.get('is_active', False)))
        sent_c, recv_c = await contact_req_service.get_requests_counts(message.from_user.id)
        await send_profile(message.chat.id, p, profile_inline_kb(lang, new_uuid, sent_c, recv_c), lang, tag_service)
    elif message.text == _("btn_delete", lang):
        success = await profile_service.delete_profile(user_id, prof_uuid)
        if success:
            await message.answer(_("prof_deleted", lang))
            await profiles_menu(message, state, lang, profile_service)
        else:
            await message.answer(_("prof_del_err", lang))