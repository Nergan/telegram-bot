import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from bot.states import ProfileSetup
from bot.keyboards import main_menu_kb, profile_inline_kb
from bot.helpers import send_profile
from core.database import Database
from core.locales import _, _btn

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("lang_en", "lang_ru", "lang_pt"))
async def switch_language(message: types.Message, state: FSMContext, lang: str):
    new_lang = message.text.split("_")[1]
    await Database.set_user_lang(message.from_user.id, new_lang)
    await message.answer(f"✅ Language updated to: {new_lang.upper()}")
    # Re-run menu loader with new lang
    await show_main_menu(message, state, lang=new_lang)

@router.message(CommandStart())
@router.message(Command("help", "hello"))
@router.message(F.text.in_(_btn("btn_view_active")))
async def show_main_menu(message: types.Message, state: FSMContext, lang: str):
    await state.clear()
    logger.info(f"User {message.from_user.id} accessed main menu.")
    
    is_help_command = message.text and message.text.startswith(("/start", "/help", "/hello"))
    if is_help_command:
        await message.answer(_("help_cmd", lang))
        
    active_profile = await Database.get_or_create_active_profile(message.from_user.id, message.from_user.username)
    
    if active_profile:
        pool_size = await Database.get_pool_size(message.from_user.id, active_profile.get("filters", {}))
        sent_c, recv_c = await Database.get_requests_counts(message.from_user.id)
        
        await message.answer(_("menu_active", lang), reply_markup=main_menu_kb(lang, pool_size, has_active=True))
        await send_profile(message.chat.id, active_profile, profile_inline_kb(lang, active_profile['public_uuid'], sent_c, recv_c), lang)
    else:
        await message.answer(_("menu_no_active", lang), reply_markup=main_menu_kb(lang, 0, has_active=False))

@router.message(StateFilter("*"), F.text.in_(_btn("btn_cancel")))
async def fsm_cancel(message: types.Message, state: FSMContext, lang: str):
    await state.clear()
    from bot.handlers.profile import edit_info_menu
    await edit_info_menu(message, lang)

@router.message(StateFilter("*"), F.text.in_(_btn("btn_clear")))
async def fsm_clear(message: types.Message, state: FSMContext, lang: str):
    curr_state = await state.get_state()
    field_map = {
        ProfileSetup.waiting_for_bio: "text",
        ProfileSetup.waiting_for_contact_val: "contacts",
        ProfileSetup.waiting_for_media: "media"
    }
    field = field_map.get(curr_state)
    if field:
        active_prof = await Database.get_active_profile(message.from_user.id)
        if active_prof:
            val = [] if field in ["media", "contacts"] else None
            await Database.db.profiles.update_one({"public_uuid": active_prof['public_uuid']}, {"$set": {field: val}})
            logger.info(f"User {message.from_user.id} cleared {field}.")
            
    await state.clear()
    from bot.handlers.profile import edit_info_menu
    await edit_info_menu(message, lang)

@router.message()
async def unhandled_message(message: types.Message, state: FSMContext, lang: str):
    curr_state = await state.get_state()
    if curr_state:
        await message.answer(_("err_fsm", lang))
    else:
        active = await Database.get_active_profile(message.from_user.id)
        if active:
            pool_size = await Database.get_pool_size(message.from_user.id, active.get("filters", {}))
            await message.answer(_("err_unknown", lang), reply_markup=main_menu_kb(lang, pool_size, True))
        else:
            has_any = await Database.db.profiles.count_documents({"user_id": message.from_user.id}) > 0
            if has_any:
                await message.answer(_("err_unknown", lang), reply_markup=main_menu_kb(lang, 0, False))
            else:
                await message.answer(_("err_start", lang))