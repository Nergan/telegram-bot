import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from bot.states import ProfileSetup
from bot.keyboards import main_menu_kb, profile_inline_kb
from bot.helpers import send_profile
from application.locales import _, _btn
from application.services import UserService, ProfileService, ContactRequestService, TagService, AlbumService

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("lang_en", "lang_ru", "lang_pt"))
async def switch_language(
    message: types.Message, state: FSMContext, lang: str, 
    user_service: UserService, profile_service: ProfileService, contact_req_service: ContactRequestService, tag_service: TagService
):
    cmd = message.text.split()[0]
    if "@" in cmd: 
        cmd = cmd.split("@")[0]
        
    new_lang = cmd.split("_")[1]
    await user_service.set_lang(message.from_user.id, new_lang)
    await message.answer(f"✅ Language updated to: {new_lang.upper()}")
    await show_main_menu(message, state, new_lang, profile_service, contact_req_service, tag_service)

@router.message(CommandStart())
@router.message(Command("help", "hello"))
@router.message(F.text.in_(_btn("btn_view_active")))
async def show_main_menu(
    message: types.Message, state: FSMContext, lang: str,
    profile_service: ProfileService, contact_req_service: ContactRequestService, tag_service: TagService
):
    await state.clear()
    logger.info(f"User {message.from_user.id} accessed main menu.")
    
    is_help_command = message.text and message.text.startswith(("/start", "/help", "/hello"))
    if is_help_command:
        await message.answer(_("help_cmd", lang))
        
    active_profile = await profile_service.get_or_create_active_profile(message.from_user.id, message.from_user.username)
    
    if active_profile:
        pool_size = await profile_service.get_pool_size(message.from_user.id, active_profile.filters)
        sent_c, recv_c = await contact_req_service.get_requests_counts(message.from_user.id)
        
        await message.answer(_("menu_active", lang), reply_markup=main_menu_kb(lang, pool_size, has_active=True))
        await send_profile(message.chat.id, active_profile, profile_inline_kb(lang, active_profile.public_uuid, sent_c, recv_c), lang, tag_service)
    else:
        await message.answer(_("menu_no_active", lang), reply_markup=main_menu_kb(lang, 0, has_active=False))

@router.message(StateFilter("*"), F.text.in_(_btn("btn_cancel")))
async def fsm_cancel(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService):
    await state.clear()
    from bot.handlers.profile import edit_info_menu
    await edit_info_menu(message, lang, profile_service)

@router.message(StateFilter("*"), F.text.in_(_btn("btn_clear")))
async def fsm_clear(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService):
    curr_state = await state.get_state()
    field_map = {
        ProfileSetup.waiting_for_bio.state: "text",
        ProfileSetup.waiting_for_media.state: "media"
    }
    
    field = field_map.get(curr_state)
    if field:
        active_prof = await profile_service.get_active_profile(message.from_user.id)
        if active_prof:
            if field == "media":
                active_prof.media = []
            else:
                active_prof.text = None
            await profile_service.update_profile(active_prof)
            logger.info(f"User {message.from_user.id} cleared {field}.")
            
    await state.clear()
    from bot.handlers.profile import edit_info_menu
    await edit_info_menu(message, lang, profile_service)

@router.message()
async def unhandled_message(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService, album_service: AlbumService):
    if message.media_group_id:
        if await album_service.is_processed(message.media_group_id):
            return

    curr_state = await state.get_state()
    if curr_state:
        await message.answer(_("err_fsm", lang))
    else:
        active = await profile_service.get_active_profile(message.from_user.id)
        if active:
            pool_size = await profile_service.get_pool_size(message.from_user.id, active.filters)
            await message.answer(_("err_unknown", lang), reply_markup=main_menu_kb(lang, pool_size, True))
        else:
            all_profs = await profile_service.get_all_by_user(message.from_user.id)
            if len(all_profs) > 0:
                await message.answer(_("err_unknown", lang), reply_markup=main_menu_kb(lang, 0, False))
            else:
                await message.answer(_("err_start", lang))