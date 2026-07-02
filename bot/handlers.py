import uuid
from aiogram import Router, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from bot.bot_setup import bot
from bot.states import ProfileSetup
from bot.keyboards import dashboard_kb, profiles_list_kb, profile_management_kb, profile_card_kb, profile_editor_kb
from core.database import Database

router = Router()

def truncate(text: str, limit: int = 800) -> str:
    if not text: return ""
    return text if len(text) <= limit else text[:limit-3] + "..."

def format_profile(profile: dict, is_dashboard: bool = False) -> str:
    text = f"<b>Profile ID:</b> <code>{profile['public_uuid']}</code>\n\n"
    
    if is_dashboard:
        text = f"🏠 <b>YOUR DASHBOARD</b>\n" + text
        
    if profile.get('text'):
        text += f"📝 {truncate(profile['text'])}\n\n"
        
    if profile.get('public_contact'):
        text += f"🌐 <b>Public Contact:</b> {truncate(profile['public_contact'], 100)}\n\n"
        
    if profile.get('tags'):
        text += f"🏷️ <b>Tags:</b> #{' #'.join(profile['tags'])}\n"
        
    if is_dashboard:
        filters = profile.get("filters", {})
        if any(filters.values()):
            text += "\n⚙️ <b>Active Filters:</b>\n"
            if filters.get("require_tags"): text += f"🟩 Must have: {', '.join(filters['require_tags'])}\n"
            if filters.get("exclude_tags"): text += f"🟥 Exclude: {', '.join(filters['exclude_tags'])}\n"
            if filters.get("any_tags"): text += f"🟦 Any of: {', '.join(filters['any_tags'])}\n"
            
    return text

async def send_or_edit_profile(message_or_callback, profile: dict, kb: types.InlineKeyboardMarkup, is_dashboard: bool = False):
    """Universal function to handle sending text or media profiles without errors."""
    text = format_profile(profile, is_dashboard)
    is_callback = isinstance(message_or_callback, types.CallbackQuery)
    msg = message_or_callback.message if is_callback else message_or_callback
    
    media_dict = profile.get("media")
    try:
        if is_callback:
            if media_dict:
                media_type = media_dict['type']
                file_id = media_dict['file_id']
                # Requires Aiogram InputMedia mapping
                if media_type == 'photo': media = types.InputMediaPhoto(media=file_id, caption=text)
                elif media_type == 'video': media = types.InputMediaVideo(media=file_id, caption=text)
                await msg.edit_media(media=media, reply_markup=kb)
            else:
                await msg.edit_text(text, reply_markup=kb)
        else:
            if media_dict:
                if media_dict['type'] == 'photo': await msg.answer_photo(photo=media_dict['file_id'], caption=text, reply_markup=kb)
                elif media_dict['type'] == 'video': await msg.answer_video(video=media_dict['file_id'], caption=text, reply_markup=kb)
                elif media_dict['type'] == 'voice': await msg.answer_voice(voice=media_dict['file_id'], caption=text, reply_markup=kb)
            else:
                await msg.answer(text, reply_markup=kb)
    except Exception:
        # Fallback if message types clash (e.g. text -> photo edit)
        if is_callback: await msg.delete()
        if media_dict:
            if media_dict['type'] == 'photo': await msg.answer_photo(photo=media_dict['file_id'], caption=text, reply_markup=kb)
            elif media_dict['type'] == 'video': await msg.answer_video(video=media_dict['file_id'], caption=text, reply_markup=kb)
            elif media_dict['type'] == 'voice': await msg.answer_voice(voice=media_dict['file_id'], caption=text, reply_markup=kb)
        else:
            await msg.answer(text, reply_markup=kb)

# --- DASHBOARD & COMMANDS ---

@router.message(CommandStart())
@router.message(Command("menu"))
@router.message(Command("dashboard"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    if len(args) > 1 and args[0] == "/start":
        target_uuid = args[1]
        profile = await Database.get_profile_by_uuid(target_uuid)
        if profile and not profile.get("is_hidden"):
            if profile['user_id'] == message.from_user.id:
                await message.answer("This is your own profile! Here is its management card:")
                await send_or_edit_profile(message, profile, profile_management_kb(profile))
            else:
                await send_or_edit_profile(message, profile, profile_card_kb(target_uuid))
            return
        else:
            await message.answer("❌ Profile not found or is hidden.")
            
    active_profile = await Database.get_or_create_active_profile(message.from_user.id)
    await send_or_edit_profile(message, active_profile, dashboard_kb(active_profile['public_uuid']), is_dashboard=True)

@router.callback_query(F.data == "dashboard")
async def dashboard_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    active_profile = await Database.get_or_create_active_profile(callback.from_user.id)
    await send_or_edit_profile(callback, active_profile, dashboard_kb(active_profile['public_uuid']), is_dashboard=True)
    await callback.answer()

# --- PROFILE EDITING (FSM) ---

@router.callback_query(F.data.startswith("edit_menu_"))
async def edit_menu_callback(callback: types.CallbackQuery):
    prof_uuid = callback.data.split("_")[2]
    await callback.message.edit_reply_markup(reply_markup=profile_editor_kb(prof_uuid))
    await callback.answer()

@router.callback_query(F.data.startswith("edit_field_"))
async def edit_field_callback(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    field = parts[2]
    prof_uuid = parts[3]
    
    await state.update_data(editing_uuid=prof_uuid)
    
    if field == "bio":
        await state.set_state(ProfileSetup.waiting_for_bio)
        await callback.message.answer("📝 Send your new Bio (text):")
    elif field == "media":
        await state.set_state(ProfileSetup.waiting_for_media)
        await callback.message.answer("📸 Send a Photo, Video, or Voice message to attach to your profile:")
    elif field == "pub":
        await state.set_state(ProfileSetup.waiting_for_pub_contact)
        await callback.message.answer("🌐 Send your Public Contact (visible to everyone):")
    elif field == "priv":
        await state.set_state(ProfileSetup.waiting_for_priv_contact)
        await callback.message.answer("🔒 Send your Private Contact (shared only upon request approval):")
        
    await callback.answer()

@router.message(ProfileSetup.waiting_for_bio)
@router.message(ProfileSetup.waiting_for_pub_contact)
@router.message(ProfileSetup.waiting_for_priv_contact)
async def capture_text_fields(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uuid = data.get('editing_uuid')
    current_state = await state.get_state()
    
    field_map = {
        ProfileSetup.waiting_for_bio: "text",
        ProfileSetup.waiting_for_pub_contact: "public_contact",
        ProfileSetup.waiting_for_priv_contact: "private_contact"
    }
    
    field = field_map[current_state]
    await Database.db.profiles.update_one({"public_uuid": uuid}, {"$set": {field: message.text}})
    await message.answer("✅ Updated successfully!")
    
    # Return to dashboard automatically
    active_profile = await Database.get_or_create_active_profile(message.from_user.id)
    await send_or_edit_profile(message, active_profile, dashboard_kb(active_profile['public_uuid']), is_dashboard=True)
    await state.clear()

@router.message(ProfileSetup.waiting_for_media)
async def capture_media_field(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uuid = data.get('editing_uuid')
    
    media_data = None
    if message.photo: media_data = {"type": "photo", "file_id": message.photo[-1].file_id}
    elif message.video: media_data = {"type": "video", "file_id": message.video.file_id}
    elif message.voice: media_data = {"type": "voice", "file_id": message.voice.file_id}
    else:
        await message.answer("Please send a valid media type (Photo, Video, Voice).")
        return
        
    await Database.db.profiles.update_one({"public_uuid": uuid}, {"$set": {"media": media_data}})
    await message.answer("✅ Media updated!")
    active_profile = await Database.get_or_create_active_profile(message.from_user.id)
    await send_or_edit_profile(message, active_profile, dashboard_kb(active_profile['public_uuid']), is_dashboard=True)
    await state.clear()

# --- PROFILE MANAGEMENT ---

@router.callback_query(F.data == "my_profiles")
async def my_profiles_callback(callback: types.CallbackQuery):
    cursor = Database.db.profiles.find({"user_id": callback.from_user.id})
    profiles = await cursor.to_list(length=10)
    
    if not profiles:
        await Database.get_or_create_active_profile(callback.from_user.id)
        cursor = Database.db.profiles.find({"user_id": callback.from_user.id})
        profiles = await cursor.to_list(length=10)
        
    text = "👥 <b>Manage Profiles</b>\nSelect an identity below."
    try: await callback.message.edit_text(text, reply_markup=profiles_list_kb(profiles))
    except Exception: await callback.message.answer(text, reply_markup=profiles_list_kb(profiles))
    await callback.answer()

@router.callback_query(F.data == "create_profile")
async def create_profile_callback(callback: types.CallbackQuery):
    await Database.create_profile(callback.from_user.id)
    await my_profiles_callback(callback)

@router.callback_query(F.data.startswith("manage_prof_"))
async def manage_prof_callback(callback: types.CallbackQuery):
    prof_uuid = callback.data.split("_")[2]
    profile = await Database.get_profile_by_uuid(prof_uuid)
    if not profile or profile['user_id'] != callback.from_user.id:
        return await callback.answer("Profile not found.", show_alert=True)
    await send_or_edit_profile(callback, profile, profile_management_kb(profile))
    await callback.answer()

@router.callback_query(F.data.startswith("set_active_"))
async def set_active_callback(callback: types.CallbackQuery):
    prof_uuid = callback.data.split("_")[2]
    await Database.set_active_profile(callback.from_user.id, prof_uuid)
    await callback.answer("🌟 Profile Activated!")
    await dashboard_callback(callback, FSMContext) # Redirect to dash

@router.callback_query(F.data.startswith("regen_id_"))
async def regen_id_callback(callback: types.CallbackQuery):
    prof_uuid = callback.data.split("_")[2]
    new_uuid = uuid.uuid4().hex[:8]
    await Database.db.profiles.update_one({"public_uuid": prof_uuid}, {"$set": {"public_uuid": new_uuid}})
    await callback.answer("🔄 ID Regenerated!")
    callback.data = f"manage_prof_{new_uuid}"
    await manage_prof_callback(callback)

@router.callback_query(F.data.startswith("delete_prof_"))
async def delete_prof_callback(callback: types.CallbackQuery):
    prof_uuid = callback.data.split("_")[2]
    await Database.delete_profile(callback.from_user.id, prof_uuid)
    await callback.answer("🗑️ Profile Deleted.")
    await my_profiles_callback(callback)

# --- BROWSING ---

@router.message(Command("browse"))
@router.callback_query(F.data == "browse_profiles" )
async def start_browsing(event: types.Message | types.CallbackQuery):
    await next_profile(event)

@router.callback_query(F.data == "next_profile")
async def next_profile(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    active_profile = await Database.get_active_profile(user_id)
    if not active_profile:
        msg = event.message if isinstance(event, types.CallbackQuery) else event
        return await msg.answer("❌ You need an active profile to browse.")

    filters = active_profile.get("filters", {})
    and_clauses = [{"user_id": {"$ne": user_id}}, {"is_active": True}, {"is_hidden": False}]
    
    if filters.get("require_tags"): and_clauses.append({"tags": {"$all": filters["require_tags"]}})
    if filters.get("exclude_tags"): and_clauses.append({"tags": {"$nin": filters["exclude_tags"]}})
    if filters.get("any_tags"): and_clauses.append({"tags": {"$in": filters["any_tags"]}})
        
    pipeline = [{"$match": {"$and": and_clauses}}, {"$sample": {"size": 1}}]
    cursor = Database.db.profiles.aggregate(pipeline)
    profiles = await cursor.to_list(length=1)
    
    if not profiles:
        if isinstance(event, types.CallbackQuery): await event.answer("No matching profiles found!", show_alert=True)
        else: await event.answer("No matching profiles found!")
        return

    profile = profiles[0]
    await send_or_edit_profile(event, profile, profile_card_kb(profile['public_uuid']))
    if isinstance(event, types.CallbackQuery): await event.answer()