import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from bot.states import ProfileSetup
from bot.keyboards import main_menu_kb, profile_inline_kb
from bot.helpers import send_profile
from core.database import Database

# Instantiate the router correctly for imports to find it
router = Router()
logger = logging.getLogger(__name__)

HELP_TEXT = """Set lang: /lang_...

This small bot acts as a bulletin board. You can use it to find people based on shared interests—whether for dating or simply for hobbies.

Your "listing" serves as your profile; you can create up to a hundred of them, though only one can be active (visible in search results) at a time.

Make sure to fill out your profile details, especially the tags. Tags allow others to find you and enable you to find others. You can also use filters to search by tags.

Configure your private and public contact details. Public contacts are displayed on your profile, while private ones are not. The bot supports two types of "likes" for other profiles: one-way contact sharing and mutual contact sharing.

With one-way sharing, you simply send your profile—including public contact details—to the user; you can also include private contact details if you choose to do so when sending the request.

With mutual sharing, your contact details are sent to the recipient only if they reveal at least one of their private contacts to you. In this case, you both simultaneously receive at least one of each other's private contacts.

You can manage incoming and outgoing requests using the corresponding inline button. While a request is pending, the user cannot send you another request of the same type.

Each profile has a unique ID for quick searching, though you can change your profile's ID at any time.

To view this message again, type /start or /help."""

@router.message(CommandStart())
@router.message(Command("help", "hello"))
@router.message(F.text == "🏠 View Active Profile")
async def show_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    logger.info(f"User {message.from_user.id} accessed main menu.")
    
    is_help_command = message.text and message.text.startswith(("/start", "/help", "/hello"))
    if is_help_command:
        await message.answer(HELP_TEXT)
        
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