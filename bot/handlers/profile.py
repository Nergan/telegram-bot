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

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "📝 Edit Active Profile")
async def edit_info_menu(message: types.Message):
    await message.answer("What would you like to edit?", reply_markup=edit_info_menu_kb())

@router.message(F.text == "✏️ Bio")
async def init_edit_bio(message: types.Message, state: FSMContext):
    await state.set_state(ProfileSetup.waiting_for_bio)
    active_prof = await Database.get_active_profile(message.from_user.id)
    has_bio = bool(active_prof.get("text")) if active_prof else False
    await message.answer("Send your new Bio:", reply_markup=edit_fsm_kb(show_clear=has_bio))

@router.message(F.text == "📸 Edit Media")
async def init_edit_media(message: types.Message, state: FSMContext):
    await state.set_state(ProfileSetup.waiting_for_media)
    active_prof = await Database.get_active_profile(message.from_user.id)
    has_media = bool(active_prof.get("media")) if active_prof else False
    await message.answer("Send a single media file, OR an album of up to 10 photos/videos in one message.", reply_markup=edit_fsm_kb(show_clear=has_media))

@router.message(ProfileSetup.waiting_for_bio)
async def capture_text(message: types.Message, state: FSMContext):
    if message.text == "❌ Cancel":
        from bot.handlers.base import fsm_cancel
        await fsm_cancel(message, state)
        return
    if message.text == "🗑️ Clear Field":
        from bot.handlers.base import fsm_clear
        await fsm_clear(message, state)
        return
    if message.content_type != 'text': 
        return await message.answer("❌ Please send text only.")
    
    active_prof = await Database.get_active_profile(message.from_user.id)
    await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {"text": message.text}})
    logger.info(f"User {message.from_user.id} updated bio.")
    
    await message.answer("✅ Bio successfully saved!", reply_markup=edit_info_menu_kb())
    await state.clear()

@router.message(ProfileSetup.waiting_for_media)
async def capture_media(message: types.Message, state: FSMContext):
    if message.text == "❌ Cancel":
        from bot.handlers.base import fsm_cancel
        await fsm_cancel(message, state)
        return
    if message.text == "🗑️ Clear Field":
        from bot.handlers.base import fsm_clear
        await fsm_clear(message, state)
        return
    valid_types = ['photo', 'video', 'voice', 'animation', 'audio', 'document']
    if message.content_type not in valid_types:
        return await message.answer("❌ Invalid media type.")
        
    active_prof = await Database.get_active_profile(message.from_user.id)
    media_doc = {"type": message.content_type}
    if message.photo: media_doc['file_id'] = message.photo[-1].file_id
    elif message.video: media_doc['file_id'] = message.video.file_id
    elif message.voice: media_doc['file_id'] = message.voice.file_id
    elif message.animation: media_doc['file_id'] = message.animation.file_id
    elif message.audio: media_doc['file_id'] = message.audio.file_id
    elif message.document: media_doc['file_id'] = message.document.file_id
    
    if message.media_group_id:
        data = await state.get_data()
        mg_id = data.get("current_mg_id")
        if mg_id != message.media_group_id:
            await state.update_data(current_mg_id=message.media_group_id)
            await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {"media": [media_doc]}})
            
            await message.answer("✅ Processing album...", reply_markup=edit_info_menu_kb())
            
            async def show_updated_profile_after_delay():
                await asyncio.sleep(1.5)
                curr_state = await state.get_state()
                if curr_state == ProfileSetup.waiting_for_media:
                    await bot.send_message(message.chat.id, "✅ Album successfully saved!", reply_markup=edit_info_menu_kb())
                    await state.clear()
            
            asyncio.create_task(show_updated_profile_after_delay())
        else:
            await Database.db.profiles.update_one(
                {"public_uuid": active_prof['public_uuid']}, 
                {"$push": {"media": {"$each": [media_doc], "$slice": 10}}}
            )
    else:
        await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {"media": [media_doc]}})
        
        await message.answer("✅ Media successfully saved!", reply_markup=edit_info_menu_kb())
        await state.clear()

@router.message(F.text == "👥 Profiles")
@router.message(F.text == "👥 View profiles again")
async def profiles_menu(message: types.Message, state: FSMContext = None):
    if state:
        await state.clear()
        
    cursor = Database.db.profiles.find({"user_id": message.from_user.id})
    profiles = await cursor.to_list(length=100)
    count = len(profiles)
    
    inline_kb = []
    for p in profiles:
        status = "🌟 Active" if p.get("is_active") else "⚪ Inactive"
        
        bio = p.get("text", "") or ""
        bio_clean = bio.strip().replace("\n", " ")
        if bio_clean:
            bio_snippet = bio_clean[:12] + "..." if len(bio_clean) > 12 else bio_clean
            label = f"📝 {bio_snippet} | ID: {p['public_uuid']} [{status}]"
        else:
            label = f"ID: {p['public_uuid']} [{status}]"
            
        inline_kb.append([InlineKeyboardButton(text=label, callback_data=f"manage_prof_{p['public_uuid']}")])
        
    await message.answer("👥 Profiles", reply_markup=profiles_menu_kb())
    if inline_kb:
        await message.answer(
            f"👥 <b>Your Profiles Pool ({count}/100)</b>\nSelect an identity below to manage it:", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb)
        )

@router.message(F.text == "➕ Create Profile")
async def create_profile_cmd(message: types.Message):
    prof = await Database.create_profile(message.from_user.id, message.from_user.username)
    if not prof:
        return await message.answer("❌ You have reached the maximum limit of 100 profiles.")
    await message.answer("✅ New profile created!")
    await profiles_menu(message)

@router.message(F.text == "🗑️ Delete All But Active")
async def del_all_but_active(message: types.Message):
    await Database.delete_all_but_active(message.from_user.id)
    await message.answer("✅ All inactive profiles deleted.")
    await profiles_menu(message)

@router.callback_query(F.data.startswith("manage_prof_"))
async def manage_prof_cb(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    
    prof_uuid = callback.data.split("_")[2]
    profile = await Database.get_profile_by_uuid(prof_uuid)
    if not profile or profile['user_id'] != callback.from_user.id:
        return await callback.answer("❌ Profile not found.", show_alert=True)
    
    await state.update_data(managing_uuid=prof_uuid)
    await callback.message.delete()
    
    is_active = profile.get('is_active', False)
    await callback.message.answer("⚙️ Managing Profile...", reply_markup=manage_action_kb(is_active))
    
    sent_c, recv_c = await Database.get_requests_counts(callback.from_user.id)
    await send_profile(callback.from_user.id, profile, profile_inline_kb(prof_uuid, sent_c, recv_c))
    await callback.answer()

@router.message(F.text.in_({"🌟 Set Active", "🔄 Regen ID", "🗑️ Delete"}))
async def manage_actions(message: types.Message, state: FSMContext):
    data = await state.get_data()
    prof_uuid = data.get("managing_uuid")
    if not prof_uuid: 
        from bot.handlers.base import show_main_menu
        return await show_main_menu(message, state)
    
    user_id = message.from_user.id
    p = await Database.get_profile_by_uuid(prof_uuid)
    if not p: 
        from bot.handlers.base import show_main_menu
        return await show_main_menu(message, state)

    if message.text == "🌟 Set Active":
        await Database.set_active_profile(user_id, prof_uuid)
        await message.answer("🌟 Profile Activated!")
        from bot.handlers.base import show_main_menu
        await show_main_menu(message, state)
    elif message.text == "🔄 Regen ID":
        new_uuid = uuid.uuid4().hex[:8]
        await Database.db.profiles.update_one({"public_uuid": prof_uuid}, {"$set": {"public_uuid": new_uuid}})
        await state.update_data(managing_uuid=new_uuid)
        p = await Database.get_profile_by_uuid(new_uuid)
        
        await message.answer("🔄 ID Regenerated!", reply_markup=manage_action_kb(p.get('is_active', False)))
        sent_c, recv_c = await Database.get_requests_counts(message.from_user.id)
        await send_profile(message.chat.id, p, profile_inline_kb(new_uuid, sent_c, recv_c))
    elif message.text == "🗑️ Delete":
        success = await Database.delete_profile(user_id, prof_uuid)
        if success:
            await message.answer("🗑️ Profile Deleted.")
            await profiles_menu(message)
        else:
            await message.answer("❌ Cannot delete your only profile.")