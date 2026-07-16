import httpx
from aiogram import Router, F
from aiogram.types import CallbackQuery, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from api_client import NetlazyAPI
from vault import get_key
from config import settings

router = Router()

@router.callback_query(F.data == "menu_profile")
async def callback_profile(call: CallbackQuery):
    key_data = await get_key(call.from_user.id)
    if not key_data:
        await call.answer("You are not logged in.", show_alert=True)
        return
        
    api = NetlazyAPI(key_data["user_id"], key_data["private_pem"])
    try:
        profile = await api.get_profile()
        
        bio = profile.get('bio', '') or 'No bio yet.'
        tags = ", ".join(profile.get('tags', [])) or "No tags."
        
        response_text = (
            f"👤 **Your Profile**\n\n"
            f"**Bio:**\n{bio}\n\n"
            f"**Tags:**\n{tags}\n"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✏️ Edit in Web App", web_app=WebAppInfo(url=settings.web_app_url))
        builder.button(text="🔙 Back", callback_data="menu_main")
        builder.adjust(1)
        
        await call.message.edit_text(response_text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except httpx.RequestError:
        await call.answer("Service waking up, try again in a few seconds.", show_alert=True)
    except Exception:
        await call.answer("Failed to load profile.", show_alert=True)