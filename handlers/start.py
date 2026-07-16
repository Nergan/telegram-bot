import httpx
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ..api_client import NetlazyAPI
from .. import key_utils

router = Router()

class LoginStates(StatesGroup):
    waiting_for_key = State()

@router.message(CommandStart())
async def cmd_start(message: Message):
    api = NetlazyAPI(message.from_user.id)
    try:
        # Check if user is already linked
        await api.get_profile()
        await message.answer("Welcome back! You are already logged in.\n\n/myprofile - View your profile\n/browse - Browse feed\n/inbox - Check messages\n/logout - Unlink this chat from your account")
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 404):
            # Not linked, so we can register
            try:
                private_pem, public_pem, user_id = key_utils.generate_keypair()
                await NetlazyAPI.bot_register(public_pem, message.from_user.id)
                
                response_text = (
                    "Welcome to netlazy! ✨\n\n"
                    "A new, secure identity has been created for you.\n\n"
                    "**⚠️ IMPORTANT ⚠️**\n"
                    "This is your private key. It's like a password. **Save it somewhere safe immediately.** "
                    "If you lose it, you will lose access to your account permanently. There is no recovery.\n\n"
                    "You can use this key to log in on the web or mobile app."
                )
                await message.answer(response_text, parse_mode="Markdown")
                await message.answer(f"`{private_pem}`", parse_mode="Markdown")

            except Exception as reg_e:
                await message.answer("Sorry, there was an error during registration. Please try again later.")
                print(f"Registration Error: {reg_e}")
        else:
            await message.answer("An unexpected error occurred. Please try again later.")
            print(f"Start command error: {e}")

@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext):
    await state.set_state(LoginStates.waiting_for_key)
    await message.answer("Please paste your full private key to link this Telegram account.")

@router.message(LoginStates.waiting_for_key, F.text)
async def process_private_key(message: Message, state: FSMContext):
    await state.clear()
    private_key_pem = message.text
    user_id = key_utils.get_user_id_from_private_key(private_key_pem)

    if not user_id:
        await message.answer("That doesn't look like a valid private key. Please try again with /login.")
        return

    try:
        await NetlazyAPI.bot_link(user_id, message.from_user.id)
        await message.answer("✅ Success! This chat is now linked to your netlazy account.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await message.answer("Account not found. It might have been deleted, or the key is incorrect.")
        else:
            await message.answer(f"An error occurred: {e.response.text}")
    except Exception as e:
        await message.answer("A server error occurred during linking.")
        print(f"Link error: {e}")
        
@router.message(Command("logout"))
async def cmd_logout(message: Message):
    try:
        await NetlazyAPI.bot_unlink(message.from_user.id)
        await message.answer("You have been successfully logged out. This chat is no longer linked to your account.\n\nUse /start to create a new identity or /login to link an existing one.")
    except Exception as e:
        await message.answer("Failed to log out. Please try again.")
        print(f"Logout error: {e}")

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "**netlazy Bot Commands**\n\n"
        "/start - Create a new identity or see your status.\n"
        "/login - Link this chat to an existing account using your private key.\n"
        "/logout - Unlink this chat from your account.\n"
        "/myprofile - View your current profile.\n"
        "/browse - Start browsing profiles.\n"
        "/inbox - Check your handshakes and matches."
    )
    await message.answer(help_text, parse_mode="Markdown")