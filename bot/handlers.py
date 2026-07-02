import uuid
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from bot.bot_setup import bot
from bot.states import ProfileSetup, ContactRequest
from bot.keyboards import *
from bot.helpers import send_profile
from core.database import Database

router = Router()

@router.message(CommandStart())
@router.message(F.text == "🏠 Dashboard")
async def show_dashboard(message: types.Message, state: FSMContext):
    await state.clear()
    active_profile = await Database.get_or_create_active_profile(message.from_user.id)
    await send_profile(message.chat.id, active_profile, dashboard_kb(active_profile['public_uuid']), is_dashboard=True)

# --- EDITING ROUTING ---

@router.message(F.text == "📝 Edit Info")
async def edit_info_menu(message: types.Message):
    await message.answer("What would you like to edit?", reply_markup=edit_info_menu_kb())

@router.message(F.text.in_({"✏️ Bio", "🌐 Public Contact", "🔒 Private Contact"}))
async def init_edit_text(message: types.Message, state: FSMContext):
    if message.text == "✏️ Bio":
        await state.set_state(ProfileSetup.waiting_for_bio)
        await message.answer("Send your new Bio:", reply_markup=edit_fsm_kb())
    elif message.text == "🌐 Public Contact":
        await state.set_state(ProfileSetup.waiting_for_pub_contact)
        await message.answer("Send your Public Contact (visible to all):", reply_markup=edit_fsm_kb())
    elif message.text == "🔒 Private Contact":
        await state.set_state(ProfileSetup.waiting_for_priv_contact)
        await message.answer("Send your Private Contact (shared only via request):", reply_markup=edit_fsm_kb())

@router.message(F.text == "📸 Edit Media")
async def init_edit_media(message: types.Message, state: FSMContext):
    await state.set_state(ProfileSetup.waiting_for_media)
    await state.update_data(temp_media=[], temp_voice=None)
    await message.answer(
        "Send up to 5 photos/videos, and/or 1 voice message.\nWhen finished, click '✅ Done'.", 
        reply_markup=edit_media_fsm_kb()
    )

# --- FSM ACTIONS (Cancel / Clear) ---

@router.message(F.text == "❌ Cancel", flags={"state": "*"})
async def fsm_cancel(message: types.Message, state: FSMContext):
    await message.answer("❌ Action cancelled.")
    await show_dashboard(message, state)

@router.message(F.text == "🗑️ Clear Field")
async def fsm_clear(message: types.Message, state: FSMContext):
    curr_state = await state.get_state()
    field = None
    if curr_state == ProfileSetup.waiting_for_bio: field = "text"
    elif curr_state == ProfileSetup.waiting_for_pub_contact: field = "public_contact"
    elif curr_state == ProfileSetup.waiting_for_priv_contact: field = "private_contact"
    elif curr_state == ProfileSetup.waiting_for_media: field = "media"
    
    if field:
        active_prof = await Database.get_active_profile(message.from_user.id)
        val = {"items": [], "voice": None} if field == "media" else None
        await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {field: val}})
        await message.answer("🗑️ Cleared.")
    await show_dashboard(message, state)

# --- FSM CAPTURE ---

@router.message(ProfileSetup.waiting_for_bio)
@router.message(ProfileSetup.waiting_for_pub_contact)
@router.message(ProfileSetup.waiting_for_priv_contact)
async def capture_text(message: types.Message, state: FSMContext):
    if message.text in ["❌ Cancel", "🗑️ Clear Field"]: return
    
    curr_state = await state.get_state()
    field = "text" if curr_state == ProfileSetup.waiting_for_bio else \
            "public_contact" if curr_state == ProfileSetup.waiting_for_pub_contact else "private_contact"
            
    active_prof = await Database.get_active_profile(message.from_user.id)
    await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {field: message.text}})
    await message.answer("✅ Saved!")
    await show_dashboard(message, state)

@router.message(ProfileSetup.waiting_for_media)
async def capture_media(message: types.Message, state: FSMContext):
    if message.text in ["❌ Cancel", "🗑️ Clear Field"]: return
    data = await state.get_data()
    temp_media = data.get("temp_media", [])
    temp_voice = data.get("temp_voice")
    
    if message.text == "✅ Done (Save)":
        active_prof = await Database.get_active_profile(message.from_user.id)
        media_doc = {"items": temp_media[:5], "voice": temp_voice}
        await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {"media": media_doc}})
        await message.answer("✅ Media saved!")
        return await show_dashboard(message, state)

    if message.photo: temp_media.append({"type": "photo", "file_id": message.photo[-1].file_id})
    elif message.video: temp_media.append({"type": "video", "file_id": message.video.file_id})
    elif message.voice: temp_voice = message.voice.file_id
    
    await state.update_data(temp_media=temp_media, temp_voice=temp_voice)

# --- PROFILES MANAGEMENT ---

@router.message(F.text == "👥 Profiles")
async def profiles_menu(message: types.Message):
    cursor = Database.db.profiles.find({"user_id": message.from_user.id})
    profiles = await cursor.to_list(length=10)
    
    text = "👥 <b>Manage Profiles</b>\nClick an ID below to manage it:\n\n"
    for p in profiles:
        status = "🌟 Active" if p.get("is_active") else "⚪ Inactive"
        if p.get("is_hidden"): status += " 👻 Hidden"
        text += f"• <code>{p['public_uuid']}</code> [{status}] 👉 /manage_{p['public_uuid']}\n"
        
    text += "\nOr /create_profile to make a new one."
    await message.answer(text, reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🏠 Dashboard")]], resize_keyboard=True))

@router.message(Command("create_profile"))
async def create_profile_cmd(message: types.Message):
    await Database.create_profile(message.from_user.id)
    await message.answer("✅ New profile created!")
    await profiles_menu(message)

@router.message(F.text.startswith("/manage_"))
async def manage_prof(message: types.Message, state: FSMContext):
    prof_uuid = message.text.split("_")[1]
    profile = await Database.get_profile_by_uuid(prof_uuid)
    if not profile or profile['user_id'] != message.from_user.id:
        return await message.answer("❌ Profile not found.")
    
    await state.update_data(managing_uuid=prof_uuid)
    await send_profile(message.chat.id, profile, manage_action_kb())

@router.message(F.text.in_({"🌟 Set Active", "👁️ Toggle Vis", "🔄 Regen ID", "🗑️ Delete"}))
async def manage_actions(message: types.Message, state: FSMContext):
    data = await state.get_data()
    prof_uuid = data.get("managing_uuid")
    if not prof_uuid: return await show_dashboard(message, state)
    
    user_id = message.from_user.id
    if message.text == "🌟 Set Active":
        await Database.set_active_profile(user_id, prof_uuid)
        await message.answer("🌟 Profile Activated!")
        await show_dashboard(message, state)
    elif message.text == "👁️ Toggle Vis":
        p = await Database.get_profile_by_uuid(prof_uuid)
        await Database.db.profiles.update_one({"public_uuid": prof_uuid}, {"$set": {"is_hidden": not p.get('is_hidden', False)}})
        await message.answer("👁️ Visibility toggled.")
        await profiles_menu(message)
    elif message.text == "🔄 Regen ID":
        new_uuid = uuid.uuid4().hex[:8]
        await Database.db.profiles.update_one({"public_uuid": prof_uuid}, {"$set": {"public_uuid": new_uuid}})
        await state.update_data(managing_uuid=new_uuid)
        await message.answer(f"🔄 ID Regenerated: {new_uuid}")
        p = await Database.get_profile_by_uuid(new_uuid)
        await send_profile(message.chat.id, p, manage_action_kb())
    elif message.text == "🗑️ Delete":
        success = await Database.delete_profile(user_id, prof_uuid)
        if success:
            await message.answer("🗑️ Profile Deleted.")
            await show_dashboard(message, state)
        else:
            await message.answer("❌ Cannot delete your only profile.")

# --- BROWSING ---

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
    
    if not profiles: return await message.answer("No matching profiles found!", reply_markup=dashboard_kb(active['public_uuid']))

    target = profiles[0]
    await state.update_data(browse_uuid=target['public_uuid'])
    await send_profile(message.chat.id, target, browse_kb())

@router.message(F.text.in_({"💌 Request Contact", "🤝 Send Contact"}))
async def init_contact(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_uuid = data.get("browse_uuid")
    if not target_uuid: return await show_dashboard(message, state)
    
    action = "req" if "Request" in message.text else "send"
    await state.update_data(target_uuid=target_uuid, action=action)
    await state.set_state(ContactRequest.waiting_for_message)
    await message.answer("Attach a message (or skip):", reply_markup=skip_message_kb())

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
    if req_doc['message']: text += f"💬: {req_doc['message']}\n"
    if data['action'] == "send": text = "🤝 <b>User shared contact!</b>\n" + text
        
    await bot.send_message(target_prof['user_id'], text, reply_markup=contact_decision_kb(req_id, is_sending=(data['action']=="send")))