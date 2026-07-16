from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from ..api_client import NetlazyAPI

router = Router()

@router.message(Command("myprofile"))
async def cmd_myprofile(message: Message):
    api = NetlazyAPI(message.from_user.id)
    try:
        profile = await api.get_profile()
        
        bio = profile.get('bio', 'No bio yet.')
        tags = ", ".join(profile.get('tags', [])) or "No tags."
        
        # We'll add media/contact display here later. For now, text is fine.
        
        response_text = (
            f"**Your Profile**\n\n"
            f"**Bio:** {bio}\n"
            f"**Tags:** {tags}\n"
        )
        
        await message.answer(response_text, parse_mode="Markdown")

    except Exception:
        await message.answer("Could not fetch your profile. Are you logged in? Use /start or /login.")