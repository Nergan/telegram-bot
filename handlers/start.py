import httpx
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, WebAppInfo
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from api_client import NetlazyAPI
from config import settings
import key_utils
from vault import get_key, save_key, delete_key

router = Router()

class LoginStates(StatesGroup):
    waiting_for_key = State()

def get_main_menu(is_logged_in: bool):
    builder = InlineKeyboardBuilder()
    web_app = WebAppInfo(url=settings.web_app_url)
    
    if is_logged_in:
        builder.button(text="👤 My Profile", callback_data="menu_profile")
        builder.button(text="📥 Inbox", callback_data="menu_inbox")
        builder.button(text="🌐 Open Web App", web_app=web_app)
        builder.button(text="⚙️ Settings", callback_data="menu_settings")
        builder.adjust(2, 1, 1)
    else:
        builder.button(text="✨ Create Identity", callback_data="auth_create")
        builder.button(text="🔑 Link Identity", callback_data="auth_link")
        builder.button(text="🌐 Open Web App", web_app=web_app)
        builder.adjust(2, 1)
    return builder.as_markup()

def is_private_chat(message: Message) -> bool:
    return message.chat.type == "private"

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if not is_private_chat(message):
        await message.answer("This only works in a private chat with me. Please DM me to continue.")
        return

    await state.clear()
    key_data = await get_key(message.from_user.id)
    
    if key_data:
        text = "Welcome back to **netlazy**! What would you like to do?"
        await message.answer(text, parse_mode="Markdown", reply_markup=get_main_menu(True))
    else:
        text = (
            "Welcome to **netlazy**! ✨\n\n"
            "Just dating. No manipulative mechanics, no aggressive monetization.\n\n"
            "Choose an option below to get started:"
        )
        await message.answer(text, parse_mode="Markdown", reply_markup=get_main_menu(False))

@router.callback_query(F.data == "auth_create")
async def callback_auth_create(call: CallbackQuery):
    await call.message.edit_text("⏳ Generating secure identity & solving Proof of Work... (this takes a few seconds)")
    
    try:
        private_pem, public_pem, user_id = key_utils.generate_keypair()
        await NetlazyAPI.register(public_pem)
        await save_key(call.from_user.id, user_id, public_pem, private_pem)
        
        stripped_key = key_utils.strip_pem(private_pem)
        
        text = (
            "✅ **Identity Created!**\n\n"
            "**⚠️ IMPORTANT ⚠️**\n"
            "Below is your private key. Tap to copy it and **save it somewhere safe immediately**. "
            "If you lose it, you lose your account forever. There is no recovery.\n\n"
            f"`{stripped_key}`"
        )
        await call.message.answer(text, parse_mode="Markdown")
        await call.message.answer("What would you like to do next?", reply_markup=get_main_menu(True))
    except httpx.RequestError:
        await call.message.answer("The service is waking up, please try again in a few seconds.", reply_markup=get_main_menu(False))
    except Exception as e:
        await call.message.answer("Sorry, there was an error during registration. Please try again later.", reply_markup=get_main_menu(False))

@router.callback_query(F.data == "auth_link")
async def callback_auth_link(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Please paste your private key below (with or without headers) to link your identity.")
    await state.set_state(LoginStates.waiting_for_key)

@router.message(LoginStates.waiting_for_key, F.text)
async def process_private_key(message: Message, state: FSMContext):
    if not is_private_chat(message): return
    
    await state.clear()
    
    private_key_pem = key_utils.restore_pem(message.text)
    user_id = key_utils.get_user_id_from_private_key(private_key_pem)

    if not user_id:
        await message.answer("That doesn't look like a valid private key. Please try again.", reply_markup=get_main_menu(False))
        return

    api = NetlazyAPI(user_id, private_key_pem)
    try:
        msg = await message.answer("⏳ Verifying identity...")
        await api.get_profile()
        _, public_pem, _ = key_utils.get_pem_and_user_id_from_private_key_string(private_key_pem)
        
        await save_key(message.from_user.id, user_id, public_pem, private_key_pem)
        
        await msg.edit_text("✅ **Success!** Identity linked.", parse_mode="Markdown")
        await message.answer("What would you like to do?", reply_markup=get_main_menu(True))
    except httpx.RequestError:
        await message.answer("The service is waking up, please try again in a few seconds.", reply_markup=get_main_menu(False))
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (404, 401):
            await message.answer("Account not found. It might have been deleted, or the key is incorrect.", reply_markup=get_main_menu(False))
        else:
            await message.answer("An error occurred connecting to the backend.", reply_markup=get_main_menu(False))
    except Exception:
        await message.answer("A server error occurred during linking.", reply_markup=get_main_menu(False))

@router.callback_query(F.data == "menu_settings")
async def callback_settings(call: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔑 Show Private Key", callback_data="settings_show_key")
    builder.button(text="🚪 Logout", callback_data="settings_logout")
    builder.button(text="🔙 Back", callback_data="menu_main")
    builder.adjust(1)
    await call.message.edit_text("⚙️ **Settings**\nManage your identity and session.", parse_mode="Markdown", reply_markup=builder.as_markup())

@router.callback_query(F.data == "menu_main")
async def callback_menu_main(call: CallbackQuery):
    await call.message.edit_text("What would you like to do?", reply_markup=get_main_menu(True))

@router.callback_query(F.data == "settings_show_key")
async def callback_show_key(call: CallbackQuery):
    key_data = await get_key(call.from_user.id)
    if not key_data:
        await call.answer("Session expired.", show_alert=True)
        return
        
    stripped_key = key_utils.strip_pem(key_data["private_pem"])
    await call.message.answer(f"Your Private Key:\n\n`{stripped_key}`", parse_mode="Markdown")
    await call.answer()

@router.callback_query(F.data == "settings_logout")
async def callback_logout(call: CallbackQuery):
    await delete_key(call.from_user.id)
    await call.message.edit_text("✅ You have been logged out.", reply_markup=get_main_menu(False))
    
@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "**netlazy Bot**\n\n"
        "This bot serves as a secure gateway to your netlazy identity.\n"
        "Use the inline buttons to interact, or open the Web App for the full experience.\n\n"
        "/start - Open the main menu"
    )
    await message.answer(help_text, parse_mode="Markdown")

@router.message(Command("language"))
async def cmd_language(message: Message):
    await message.answer("Use the Web App to toggle your preferred UI language!")