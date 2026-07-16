import httpx
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from api_client import NetlazyAPI
from vault import get_key

router = Router()

@router.message(Command("myprofile"))
async def cmd_myprofile(message: Message):
    if message.chat.type != "private":
        await message.answer("This only works in a private chat with me.")
        return
        
    key_data = await get_key(message.from_user.id)
    if not key_data:
        await message.answer("You are not logged in. Use /start or /login.")
        return
        
    api = NetlazyAPI(key_data["user_id"], key_data["private_pem"])
    try:
        profile = await api.get_profile()
        
        bio = profile.get('bio', 'No bio yet.')
        tags = ", ".join(profile.get('tags', [])) or "No tags."
        
        response_text = (
            f"**Your Profile**\n\n"
            f"**Bio:** {bio}\n"
            f"**Tags:** {tags}\n"
        )
        
        await message.answer(response_text, parse_mode="Markdown")
    except httpx.RequestError:
        await message.answer("The service is waking up, please try again in a few seconds.")
    except Exception:
        await message.answer("Could not fetch your profile. Are you logged in? Use /start or /login.")