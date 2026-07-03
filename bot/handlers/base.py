import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from bot.states import ProfileSetup
from bot.keyboards import main_menu_kb, profile_inline_kb
from bot.helpers import send_profile
from core.database import Database

router = Router()
logger = logging.getLogger(__name__)

@router.message(CommandStart())
@router.message(F.text == "🏠 View Active Profile")
async def show_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    logger.info(f"User {message.from_user.id} accessed main menu.")
    active_profile = await Database.get_or_create_active_profile(message.from_user.id, message.from_user.username)
    
    pool_size = await Database.get_pool_size(message.from_user.id)
    sent_c, recv_c = await Database.get_requests_counts(message.from_user.id)
    
    await message.answer("🏠 View Active Profile 🏠", reply_markup=main_menu_kb(pool_size))
    await send_profile(message.chat.id, active_profile, profile_inline_kb(active_profile['public_uuid'], sent_c, recv_c))

@router.message(StateFilter("*"), F.text == "❌ Cancel")
async def fsm_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    from bot.handlers.profile import edit_info_menu
    await edit_info_menu(message)

@router.message(StateFilter("*"), F.text == "🗑️ Clear Field")
async def fsm_clear(message: types.Message, state: FSMContext):
    curr_state = await state.get_state()
    field_map = {
        ProfileSetup.waiting_for_bio: "text",
        ProfileSetup.waiting_for_contact_val: "contacts",
        ProfileSetup.waiting_for_media: "media"
    }
    field = field_map.get(curr_state)
    if field:
        active_prof = await Database.get_active_profile(message.from_user.id)
        val = [] if field in ["media", "contacts"] else None
        await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {field: val}})
        logger.info(f"User {message.from_user.id} cleared {field}.")
    await state.clear()
    from bot.handlers.profile import edit_info_menu
    await edit_info_menu(message)

@router.message()
async def unhandled_message(message: types.Message, state: FSMContext):
    curr_state = await state.get_state()
    if curr_state:
        await message.answer("❌ Invalid input for this step. Please correct it or press '❌ Cancel'.")
    else:
        active = await Database.get_active_profile(message.from_user.id)
        if active:
            pool_size = await Database.get_pool_size(message.from_user.id)
            await message.answer("🤷 Unrecognized command. Please use the menu buttons below.", reply_markup=main_menu_kb(pool_size))
        else:
            await message.answer("🤷 Send /start to begin.")