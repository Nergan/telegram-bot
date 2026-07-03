import uuid
import html
import asyncio
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from bot.bot_setup import bot
from bot.states import ProfileSetup, ContactRequest
from bot.keyboards import *
from bot.helpers import send_profile
from core.database import Database

router = Router()

@router.message(CommandStart())
# Обработчик переименован на "🏠 View Active Profile"
@router.message(F.text == "🏠 View Active Profile")
async def show_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    active_profile = await Database.get_or_create_active_profile(message.from_user.id)
    
    # Отправляем только эмодзи-маркер для бесшовного обновления Reply-клавиатуры
    await message.answer("🏠", reply_markup=main_menu_kb())
    # Сразу присылаем саму анкету
    await send_profile(message.chat.id, active_profile, profile_inline_kb(active_profile['public_uuid']))

@router.message(F.text == "🔒 View Private Contacts")
async def view_private_contacts(message: types.Message):
    active_prof = await Database.get_active_profile(message.from_user.id)
    priv = active_prof.get('private_contact')
    if priv: await message.answer(f"🔒 <b>Your Private Contacts:</b>\n\n{html.escape(priv)}")
    else: await message.answer("🔒 You have not set any Private Contacts yet.")

# --- EDITING ROUTING ---

@router.message(F.text == "📝 Edit Info")
async def edit_info_menu(message: types.Message):
    await message.answer("What would you like to edit?", reply_markup=edit_info_menu_kb())

@router.message(F.text.in_({"✏️ Bio", "🌐 Public Contacts", "🔒 Private Contacts"}))
async def init_edit_text(message: types.Message, state: FSMContext):
    if message.text == "✏️ Bio":
        await state.set_state(ProfileSetup.waiting_for_bio)
        await message.answer("Send your new Bio:", reply_markup=edit_fsm_kb())
    elif message.text == "🌐 Public Contacts":
        await state.set_state(ProfileSetup.waiting_for_pub_contact)
        await message.answer("Send your Public Contacts:", reply_markup=edit_fsm_kb())
    elif message.text == "🔒 Private Contacts":
        await state.set_state(ProfileSetup.waiting_for_priv_contact)
        await message.answer("Send your Private Contacts:", reply_markup=edit_fsm_kb())

@router.message(F.text == "📸 Edit Media")
async def init_edit_media(message: types.Message, state: FSMContext):
    await state.set_state(ProfileSetup.waiting_for_media)
    await message.answer("Send a single media file, OR an album of up to 10 photos/videos in one message.", reply_markup=edit_fsm_kb())

# --- FSM ACTIONS (Cancel / Clear) ---

@router.message(F.text == "❌ Cancel", flags={"state": "*"})
async def fsm_cancel(message: types.Message, state: FSMContext):
    await show_main_menu(message, state)

@router.message(F.text == "🗑️ Clear Field")
async def fsm_clear(message: types.Message, state: FSMContext):
    curr_state = await state.get_state()
    field_map = {
        ProfileSetup.waiting_for_bio: "text",
        ProfileSetup.waiting_for_pub_contact: "public_contact",
        ProfileSetup.waiting_for_priv_contact: "private_contact",
        ProfileSetup.waiting_for_media: "media"
    }
    field = field_map.get(curr_state)
    if field:
        active_prof = await Database.get_active_profile(message.from_user.id)
        val = [] if field == "media" else None
        await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {field: val}})
    await show_main_menu(message, state)

# --- FSM CAPTURE ---

@router.message(ProfileSetup.waiting_for_bio)
@router.message(ProfileSetup.waiting_for_pub_contact)
@router.message(ProfileSetup.waiting_for_priv_contact)
async def capture_text(message: types.Message, state: FSMContext):
    if message.text in ["❌ Cancel", "🗑️ Clear Field"]: return
    if message.content_type != 'text': return await message.answer("❌ Please send text only.")
    
    curr_state = await state.get_state()
    field = "text" if curr_state == ProfileSetup.waiting_for_bio else \
            "public_contact" if curr_state == ProfileSetup.waiting_for_pub_contact else "private_contact"
            
    active_prof = await Database.get_active_profile(message.from_user.id)
    await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {field: message.text}})
    await message.answer("✅ Saved!")
    
    updated = await Database.get_active_profile(message.from_user.id)
    await send_profile(message.chat.id, updated, profile_inline_kb(updated['public_uuid']))
    await state.clear()

@router.message(ProfileSetup.waiting_for_media)
async def capture_media(message: types.Message, state: FSMContext):
    if message.text in ["❌ Cancel", "🗑️ Clear Field"]: return
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
            await message.answer("✅ Processing album...")
            
            async def show_updated_profile_after_delay():
                await asyncio.sleep(1.5)
                curr_state = await state.get_state()
                if curr_state == ProfileSetup.waiting_for_media:
                    updated = await Database.get_active_profile(message.from_user.id)
                    await send_profile(message.chat.id, updated, profile_inline_kb(updated['public_uuid']))
                    await state.clear()
            
            asyncio.create_task(show_updated_profile_after_delay())
        else:
            await Database.db.profiles.update_one(
                {"public_uuid": active_prof['public_uuid']}, 
                {"$push": {"media": {"$each": [media_doc], "$slice": 10}}}
            )
    else:
        await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {"media": [media_doc]}})
        await message.answer("✅ Media saved!")
        updated = await Database.get_active_profile(message.from_user.id)
        await send_profile(message.chat.id, updated, profile_inline_kb(updated['public_uuid']))
        await state.clear()

# --- PROFILES MANAGEMENT ---

@router.message(F.text == "👥 Profiles")
async def profiles_menu(message: types.Message):
    cursor = Database.db.profiles.find({"user_id": message.from_user.id})
    profiles = await cursor.to_list(length=100)
    count = len(profiles)
    
    inline_kb = []
    for p in profiles:
        status = "🌟 Active" if p.get("is_active") else "⚪ Inactive"
        if p.get("is_hidden"): status += " 👻 Hidden"
        inline_kb.append([InlineKeyboardButton(text=f"{p['public_uuid']} [{status}]", callback_data=f"manage_prof_{p['public_uuid']}")])
        
    # 1. Отправляем эмодзи-маркер для переключения Reply-клавиатуры
    await message.answer("👥", reply_markup=profiles_menu_kb())
    
    # 2. Объединено: Выводим сводку по профилям и список с инлайн-кнопками в ОДНОМ красивом сообщении
    if inline_kb:
        await message.answer(
            f"👥 <b>Your Profiles Pool ({count}/100)</b>\nSelect an identity below to manage it:", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb)
        )

@router.message(F.text == "➕ Create Profile")
async def create_profile_cmd(message: types.Message):
    prof = await Database.create_profile(message.from_user.id)
    if not prof:
        return await message.answer("❌ You have reached the maximum limit of 100 profiles.")
    await message.answer("✅ New profile created!")
    await profiles_menu(message)

@router.message(F.text == "🗑️ Delete All But Active")
async def del_all_but_active(message: types.Message):
    await Database.delete_all_but_active(message.from_user.id)
    await message.answer("✅ All inactive profiles deleted.")
    await profiles_menu(message)

@router.message(F.text == "💣 Delete All Profiles")
async def request_del_all(message: types.Message, state: FSMContext):
    await state.set_state(ProfileSetup.waiting_for_delete_all)
    await message.answer("⚠️ <b>WARNING:</b> This will permanently delete ALL your profiles.\nAre you absolutely sure?", reply_markup=confirm_delete_all_kb())

@router.message(ProfileSetup.waiting_for_delete_all)
async def confirm_del_all(message: types.Message, state: FSMContext):
    if message.text == "⚠️ YES, DELETE ALL PROFILES":
        await Database.delete_all_profiles(message.from_user.id)
        await message.answer("✅ All profiles completely wiped.\nA new blank profile will be created.")
        await state.clear()
        await show_main_menu(message, state)
    else:
        await fsm_cancel(message, state)

@router.callback_query(F.data.startswith("manage_prof_"))
async def manage_prof_cb(callback: types.CallbackQuery, state: FSMContext):
    prof_uuid = callback.data.split("_")[2]
    profile = await Database.get_profile_by_uuid(prof_uuid)
    if not profile or profile['user_id'] != callback.from_user.id:
        return await callback.answer("❌ Profile not found.", show_alert=True)
    
    await state.update_data(managing_uuid=prof_uuid)
    await callback.message.delete()
    await send_profile(callback.from_user.id, profile, manage_action_kb())
    await callback.answer()

@router.message(F.text.in_({"🌟 Set Active", "👁️ Toggle Vis", "🔄 Regen ID", "🗑️ Delete"}))
async def manage_actions(message: types.Message, state: FSMContext):
    data = await state.get_data()
    prof_uuid = data.get("managing_uuid")
    if not prof_uuid: return await show_main_menu(message, state)
    
    user_id = message.from_user.id
    p = await Database.get_profile_by_uuid(prof_uuid)
    if not p: return await show_main_menu(message, state)

    if message.text == "🌟 Set Active":
        await Database.set_active_profile(user_id, prof_uuid)
        await message.answer("🌟 Profile Activated!")
        await show_main_menu(message, state)
    elif message.text == "👁️ Toggle Vis":
        await Database.db.profiles.update_one({"public_uuid": prof_uuid}, {"$set": {"is_hidden": not p.get('is_hidden', False)}})
        await message.answer("👁️ Visibility toggled.")
        await profiles_menu(message)
    elif message.text == "🔄 Regen ID":
        new_uuid = uuid.uuid4().hex[:8]
        await Database.db.profiles.update_one({"public_uuid": prof_uuid}, {"$set": {"public_uuid": new_uuid}})
        await state.update_data(managing_uuid=new_uuid)
        p = await Database.get_profile_by_uuid(new_uuid)
        await send_profile(message.chat.id, p, manage_action_kb())
    elif message.text == "🗑️ Delete":
        success = await Database.delete_profile(user_id, prof_uuid)
        if success:
            await message.answer("🗑️ Profile Deleted.")
            await profiles_menu(message)
        else:
            await message.answer("❌ Cannot delete your only profile.")

# --- BROWSING ---

@router.message(Command("browse"))
@router.message(F.text.in_({"🔍 Browse", "⏩ Next Profile"}))
async def browse_next(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    active = await Database.get_active_profile(user_id)
    
    filters = active.get("filters", {})
    and_clauses = [{"user_id": {"$ne": user_id}}, {"is_active": True}, {"is_hidden": False}]
    if filters.get("require_tags"): and_clauses.append({"tags": {"$all": filters["require_tags"]}})
    if filters.get("exclude_tags"): and_clauses.append({"tags": {"$nin": filters["exclude_tags"]}})
    if filters.get("any_tags"): and_clauses.append({"tags": {"$in": filters["any_tags"]}})
        
    cursor = Database.db.profiles.aggregate([{"$match": {"$and": and_clauses}}, {"$sample": {"size": 1}}])
    profiles = await cursor.to_list(length=1)
    
    if not profiles: return await message.answer("No matching profiles found!", reply_markup=main_menu_kb())

    target = profiles[0]
    await state.update_data(browse_uuid=target['public_uuid'])
    await send_profile(message.chat.id, target, browse_kb())

@router.message(F.text.in_({"💌 Request Contact", "🤝 Send Contact"}))
async def init_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_uuid = data.get("browse_uuid")
    if not target_uuid: return await show_main_menu(message, state)
    
    action = "req" if "Request" in message.text else "send"
    await state.update_data(target_uuid=target_uuid, action=action)
    await state.set_state(ContactRequest.waiting_for_message)
    await message.answer("Attach a message (or click skip):", reply_markup=skip_message_kb())

@router.callback_query(F.data == "skip_req_msg", ContactRequest.waiting_for_message)
async def skip_contact_msg(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await execute_contact_request(callback.from_user.id, state)
    await callback.message.answer("✅ Request sent!", reply_markup=browse_kb())

@router.message(ContactRequest.waiting_for_message)
async def capture_contact_msg(message: types.Message, state: FSMContext):
    await execute_contact_request(message.from_user.id, state, message)
    await message.answer("✅ Request sent with message!", reply_markup=browse_kb())

async def execute_contact_request(user_id: int, state: FSMContext, message=None):
    data = await state.get_data()
    target_prof = await Database.get_profile_by_uuid(data['target_uuid'])
    if not target_prof: return
    
    req_id = uuid.uuid4().hex
    req_doc = {"req_id": req_id, "initiator_id": user_id, "target_id": target_prof['user_id'], "action": data['action'], "status": "pending", "message": message.text if message else None}
    await Database.db.contact_requests.insert_one(req_doc)
    
    initiator = await Database.get_active_profile(user_id)
    text = f"🔔 <b>Contact Request!</b>\nFrom: {initiator['public_uuid']}\n"
    if req_doc['message']: text += f"💬: {html.escape(req_doc['message'])}\n"
    if data['action'] == "send": text = "🤝 <b>User shared contact!</b>\n" + text
        
    await bot.send_message(target_prof['user_id'], text, reply_markup=contact_decision_kb(req_id, is_sending=(data['action']=="send")))

# --- AD-HOC COMMANDS HANDLERS ---

@router.message(Command("search"))
async def search_cmd(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Please provide an ID. Example: `/search a1b2c3d4`", parse_mode="Markdown")
        return
    
    profile = await Database.get_profile_by_uuid(args[1])
    if profile:
        await send_profile(message.chat.id, profile, profile_card_kb(profile['public_uuid']))
    else:
        await message.answer("❌ Profile not found.")

# --- FALLBACK HANDLER ---
@router.message()
async def unhandled_message(message: types.Message, state: FSMContext):
    curr_state = await state.get_state()
    if curr_state:
        await message.answer("❌ Invalid input for this step. Please correct it or press '❌ Cancel'.")
    else:
        active = await Database.get_active_profile(message.from_user.id)
        if active:
            await message.answer("🤷 Unrecognized command. Please use the menu buttons below.", reply_markup=main_menu_kb())
        else:
            await message.answer("🤷 Send /start to begin.")