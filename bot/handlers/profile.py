import uuid
import logging
import asyncio
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.bot_setup import bot
from bot.states import ProfileSetup
from bot.keyboards import (
    edit_info_menu_kb,
    edit_fsm_kb,
    profiles_menu_kb,
    manage_action_kb,
    profile_inline_kb
)
from bot.helpers import send_profile
from core.database import Database
from core.locales import _, _btn

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text.in_(_btn("btn_edit_active")))
async def edit_info_menu(message: types.Message, lang: str):
    await message.answer(_("menu_edit", lang), reply_markup=edit_info_menu_kb(lang))

@router.message(F.text.in_(_btn("btn_bio")))
async def init_edit_bio(message: types.Message, state: FSMContext, lang: str):
    await state.set_state(ProfileSetup.waiting_for_bio)
    active_prof = await Database.get_active_profile(message.from_user.id)
    has_bio = bool(active_prof.get("text")) if active_prof else False
    await message.answer(_("send_bio", lang), reply_markup=edit_fsm_kb(lang, show_clear=has_bio))

@router.message(F.text.in_(_btn("btn_media")))
async def init_edit_media(message: types.Message, state: FSMContext, lang: str):
    await state.set_state(ProfileSetup.waiting_for_media)
    active_prof = await Database.get_active_profile(message.from_user.id)
    has_media = bool(active_prof.get("media")) if active_prof else False
    await message.answer(_("send_media", lang), reply_markup=edit_fsm_kb(lang, show_clear=has_media))

@router.message(ProfileSetup.waiting_for_bio)
async def capture_text(message: types.Message, state: FSMContext, lang: str):
    if message.text == _("btn_cancel", lang):
        from bot.handlers.base import fsm_cancel
        await fsm_cancel(message, state, lang)
        return
    if message.text == _("btn_clear", lang):
        from bot.handlers.base import fsm_clear
        await fsm_clear(message, state, lang)
        return
    if message.content_type != 'text': 
        return await message.answer(_("invalid_text", lang))
    
    active_prof = await Database.get_active_profile(message.from_user.id)
    await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {"text": message.text}})
    
    await message.answer(_("bio_saved", lang), reply_markup=edit_info_menu_kb(lang))
    await state.clear()

@router.message(ProfileSetup.waiting_for_media)
async def capture_media(message: types.Message, state: FSMContext, lang: str):
    if message.text == _("btn_cancel", lang):
        from bot.handlers.base import fsm_cancel
        await fsm_cancel(message, state, lang)
        return
    if message.text == _("btn_clear", lang):
        from bot.handlers.base import fsm_clear
        await fsm_clear(message, state, lang)
        return
    valid_types = ['photo', 'video', 'voice', 'animation', 'audio', 'document']
    if message.content_type not in valid_types:
        return await message.answer(_("invalid_media", lang))
        
    active_prof = await Database.get_active_profile(message.from_user.id)
    if not active_prof:
        return await message.answer(_("prof_not_found", lang))

    media_doc = {"type": message.content_type}
    if message.photo: media_doc['file_id'] = message.photo[-1].file_id
    elif message.video: media_doc['file_id'] = message.video.file_id
    elif message.voice: media_doc['file_id'] = message.voice.file_id
    elif message.animation: media_doc['file_id'] = message.animation.file_id
    elif message.audio: media_doc['file_id'] = message.audio.file_id
    elif message.document: media_doc['file_id'] = message.document.file_id
    
    if message.media_group_id:
        # Check FSM context data to see if we've already started processing this album
        state_data = await state.get_data()
        current_group_id = state_data.get("media_group_id")
        
        if current_group_id != message.media_group_id:
            # FIRST message of the album: Wipe existing media and set the first item
            await state.update_data(media_group_id=message.media_group_id)
            await Database.db.profiles.update_one(
                {"public_uuid": active_prof['public_uuid']}, 
                {"$set": {"media": [media_doc]}}
            )
            
            await message.answer(_("album_proc", lang))
            await asyncio.sleep(1.5)
            
            # Verify the state context is still valid for this album before closing it out
            fresh_data = await state.get_data()
            if fresh_data.get("media_group_id") == message.media_group_id:
                await state.clear()
                await message.answer(_("album_saved", lang), reply_markup=edit_info_menu_kb(lang))
        else:
            # SUBSEQUENT messages of the same album: Append them to the newly replaced list
            await Database.db.profiles.update_one(
                {"public_uuid": active_prof['public_uuid']}, 
                {"$push": {"media": media_doc}}
            )
    else:
        # Single media upload: Completely replace existing media with the single new item
        await Database.db.profiles.update_one(
            {"public_uuid": active_prof['public_uuid']}, 
            {"$set": {"media": [media_doc]}}
        )
        await message.answer(_("media_saved", lang), reply_markup=edit_info_menu_kb(lang))
        await state.clear()

@router.message(F.text.in_(_btn("btn_profiles")))
async def profiles_menu(message: types.Message, state: FSMContext = None, lang: str = "en"):
    if state: await state.clear()
    profiles = await Database.db.profiles.find({"user_id": message.from_user.id}).to_list(length=100)
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
        await message.answer(
            _("profiles_header", lang, count), 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb)
        )

@router.message(F.text.in_(_btn("btn_create")))
async def create_profile_cmd(message: types.Message, lang: str):
    prof = await Database.create_profile(message.from_user.id, message.from_user.username)
    if not prof:
        return await message.answer(_("prof_limit", lang))
    await message.answer(_("prof_created", lang))
    await profiles_menu(message, lang=lang)

@router.message(F.text.in_(_btn("btn_del_all")))
async def del_all_but_active(message: types.Message, lang: str):
    await Database.delete_all_but_active(message.from_user.id)
    await message.answer(_("prof_del_inactive", lang))
    await profiles_menu(message, lang=lang)

@router.callback_query(F.data.startswith("manage_prof_"))
async def manage_prof_cb(callback: types.CallbackQuery, state: FSMContext, lang: str):
    await state.clear()
    prof_uuid = callback.data.split("_")[2]
    profile = await Database.get_profile_by_uuid(prof_uuid)
    if not profile or profile['user_id'] != callback.from_user.id:
        return await callback.answer(_("prof_not_found", lang), show_alert=True)
    
    await state.update_data(managing_uuid=prof_uuid)
    await callback.message.delete()
    
    is_active = profile.get('is_active', False)
    await callback.message.answer(_("prof_managing", lang), reply_markup=manage_action_kb(lang, is_active))
    
    sent_c, recv_c = await Database.get_requests_counts(callback.from_user.id)
    await send_profile(callback.from_user.id, profile, profile_inline_kb(lang, prof_uuid, sent_c, recv_c), lang)
    await callback.answer()

@router.message(F.text.in_(_btn("btn_set_active")) | F.text.in_(_btn("btn_regen_id")) | F.text.in_(_btn("btn_delete")) | F.text.in_(_btn("btn_view_again")))
async def manage_actions(message: types.Message, state: FSMContext, lang: str):
    data = await state.get_data()
    prof_uuid = data.get("managing_uuid")
    if not prof_uuid or message.text == _("btn_view_again", lang): 
        return await profiles_menu(message, state, lang)
    
    user_id = message.from_user.id
    p = await Database.get_profile_by_uuid(prof_uuid)
    if not p: 
        return await profiles_menu(message, state, lang)

    if message.text == _("btn_set_active", lang):
        await Database.set_active_profile(user_id, prof_uuid)
        await message.answer(_("prof_activated", lang))
        from bot.handlers.base import show_main_menu
        await show_main_menu(message, state, lang)
    elif message.text == _("btn_regen_id", lang):
        new_uuid = uuid.uuid4().hex[:8]
        await Database.db.profiles.update_one({"public_uuid": prof_uuid}, {"$set": {"public_uuid": new_uuid}})
        await state.update_data(managing_uuid=new_uuid)
        p = await Database.get_profile_by_uuid(new_uuid)
        
        await message.answer(_("prof_regen", lang), reply_markup=manage_action_kb(lang, p.get('is_active', False)))
        sent_c, recv_c = await Database.get_requests_counts(message.from_user.id)
        await send_profile(message.chat.id, p, profile_inline_kb(lang, new_uuid, sent_c, recv_c), lang)
    elif message.text == _("btn_delete", lang):
        success = await Database.delete_profile(user_id, prof_uuid)
        if success:
            await message.answer(_("prof_deleted", lang))
            await profiles_menu(message, lang=lang)
        else:
            await message.answer(_("prof_del_err", lang))