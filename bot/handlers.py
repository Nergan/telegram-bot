import uuid
from aiogram import Router, F, types
from aiogram.filters import Command, CommandStart
from bot.bot_setup import bot
from bot.keyboards import main_menu_kb, profiles_list_kb, profile_management_kb, profile_card_kb
from core.database import Database

router = Router()
creating_profiles_users = set()

def format_profile(profile_data: dict) -> str:
    text = f"<b>Profile ID:</b> <code>{profile_data.get('public_uuid')}</code>\n\n"
    if profile_data.get('text'):
        text += f"📝 {profile_data['text']}\n\n"
    if profile_data.get('tags'):
        text += f"🏷️ <b>Tags:</b> #{' #'.join(profile_data['tags'])}"
    return text

# --- COMMANDS ---

@router.message(CommandStart())
async def start_cmd(message: types.Message):
    args = message.text.split()
    if len(args) > 1:
        # Deep Linking logic
        target_uuid = args[1]
        profile = await Database.get_profile_by_uuid(target_uuid)
        if profile and not profile.get("is_hidden"):
            await message.answer("🔍 Found profile via link:\n" + format_profile(profile), reply_markup=profile_card_kb(target_uuid))
            return
        else:
            await message.answer("❌ Profile not found or is hidden.")
            
    await message.answer("Welcome to Day Dating! Select an option below:", reply_markup=main_menu_kb())

@router.message(Command("menu"))
async def menu_cmd(message: types.Message):
    await message.answer("Main Menu:", reply_markup=main_menu_kb())

@router.message(Command("profiles"))
async def profiles_cmd(message: types.Message):
    await my_profiles_callback(message)

@router.message(Command("search"))
async def search_cmd(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Please provide an ID. Example: `/search a1b2c3d4`", parse_mode="Markdown")
        return
    
    profile = await Database.get_profile_by_uuid(args[1])
    if profile:
        await message.answer(format_profile(profile), reply_markup=profile_card_kb(profile['public_uuid']))
    else:
        await message.answer("❌ Profile not found.")

# --- NAVIGATION & PROFILES ---

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery):
    await callback.message.edit_text("Main Menu:", reply_markup=main_menu_kb())

@router.callback_query(F.data.in_({"my_profile", "my_profiles"}))
async def my_profiles_callback(callback: types.CallbackQuery | types.Message):
    user_id = callback.from_user.id
    
    # Сразу отправляем callback.answer с текстом, чтобы убрать спиннер загрузки кнопки 
    # и показать пользователю, что запрос принят.
    if isinstance(callback, types.CallbackQuery):
        await callback.answer("Loading your profiles...", show_alert=False)
        
    # Защита от дребезга контактов (double-click):
    # Если пользователь уже находится в процессе создания профиля, игнорируем повторный вызов
    if user_id in creating_profiles_users:
        return

    cursor = Database.db.profiles.find({"user_id": user_id, "is_deleted": False})
    profiles = await cursor.to_list(length=10)
    
    if not profiles:
        creating_profiles_users.add(user_id)  # Блокируем новые запросы от этого пользователя
        try:
            await Database.create_profile(user_id)
            cursor = Database.db.profiles.find({"user_id": user_id, "is_deleted": False})
            profiles = await cursor.to_list(length=10)
        finally:
            creating_profiles_users.discard(user_id)  # Обязательно снимаем блокировку в блоке finally
        
    text = "👤 <b>Your Profiles</b>\nManage your identities below. Only one can be Active for browsing."
    kb = profiles_list_kb(profiles)
    
    if isinstance(callback, types.CallbackQuery):
        await callback.message.edit_text(text, reply_markup=kb)
    else:
        await callback.answer(text, reply_markup=kb)

@router.callback_query(F.data == "create_profile")
async def create_profile_callback(callback: types.CallbackQuery):
    await Database.create_profile(callback.from_user.id)
    await callback.answer("✅ New profile created!")
    await my_profiles_callback(callback)

@router.callback_query(F.data.startswith("manage_prof_"))
async def manage_prof_callback(callback: types.CallbackQuery):
    prof_uuid = callback.data.split("_")[2]
    profile = await Database.get_profile_by_uuid(prof_uuid)
    if not profile or profile['user_id'] != callback.from_user.id:
        return await callback.answer("Profile not found.", show_alert=True)
    
    await callback.message.edit_text(f"⚙️ <b>Managing Profile:</b> {prof_uuid}\n\n" + format_profile(profile), reply_markup=profile_management_kb(profile))

@router.callback_query(F.data.startswith("set_active_"))
async def set_active_callback(callback: types.CallbackQuery):
    prof_uuid = callback.data.split("_")[2]
    await Database.set_active_profile(callback.from_user.id, prof_uuid)
    await callback.answer("🌟 Profile set as Active!")
    await my_profiles_callback(callback)

@router.callback_query(F.data.startswith("toggle_hide_"))
async def toggle_hide_callback(callback: types.CallbackQuery):
    prof_uuid = callback.data.split("_")[2]
    profile = await Database.get_profile_by_uuid(prof_uuid)
    new_state = not profile.get('is_hidden', False)
    await Database.db.profiles.update_one({"public_uuid": prof_uuid}, {"$set": {"is_hidden": new_state}})
    await callback.answer(f"Profile {'hidden' if new_state else 'unhidden'}!")
    await manage_prof_callback(callback) # Refresh

@router.callback_query(F.data.startswith("regen_id_"))
async def regen_id_callback(callback: types.CallbackQuery):
    prof_uuid = callback.data.split("_")[2]
    new_uuid = uuid.uuid4().hex[:8]
    await Database.db.profiles.update_one({"public_uuid": prof_uuid}, {"$set": {"public_uuid": new_uuid}})
    await callback.answer("🔄 ID Regenerated!")
    callback.data = f"manage_prof_{new_uuid}" # Patch callback data for refresh
    await manage_prof_callback(callback)

@router.callback_query(F.data.startswith("delete_prof_"))
async def delete_prof_callback(callback: types.CallbackQuery):
    prof_uuid = callback.data.split("_")[2]
    await Database.db.profiles.update_one({"public_uuid": prof_uuid}, {"$set": {"is_deleted": True, "is_active": False}})
    await callback.answer("🗑️ Profile deleted.")
    await my_profiles_callback(callback)

# --- BROWSING ---

@router.callback_query(F.data == "browse_profiles" )
async def start_browsing(callback: types.CallbackQuery):
    await next_profile(callback)

@router.callback_query(F.data == "next_profile")
async def next_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = await Database.db.search_sessions.find_one({"user_id": user_id})
    filters = session.get("filters", {}) if session else {}

    # Build Mongo Query
    and_clauses = [
        {"user_id": {"$ne": user_id}}, 
        {"is_active": True}, 
        {"is_hidden": False}, 
        {"is_deleted": False}
    ]
    
    if filters.get("require_tags"):
        and_clauses.append({"tags": {"$all": filters["require_tags"]}})
    if filters.get("exclude_tags"):
        and_clauses.append({"tags": {"$nin": filters["exclude_tags"]}})
    if filters.get("any_tags"):
        and_clauses.append({"tags": {"$in": filters["any_tags"]}})
        
    pipeline = [{"$match": {"$and": and_clauses}}, {"$sample": {"size": 1}}]
    cursor = Database.db.profiles.aggregate(pipeline)
    profiles = await cursor.to_list(length=1)
    
    if not profiles:
        await callback.answer("No more profiles matching your filters!", show_alert=True)
        return

    profile = profiles[0]
    text = format_profile(profile)
    kb = profile_card_kb(profile['public_uuid'])

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb)
        
    await callback.answer()

# --- CATCH-ALL FALLBACK ---
@router.message()
async def unhandled_message_fallback(message: types.Message):
    await message.answer(
        "🤷 I didn't quite catch that.\n"
        "Please use the menu buttons or type /menu.",
        reply_markup=main_menu_kb()
    )