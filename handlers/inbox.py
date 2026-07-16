import httpx
from aiogram import Router, F
from aiogram.types import CallbackQuery, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from api_client import NetlazyAPI
from vault import get_key
from config import settings

router = Router()

@router.callback_query(F.data == "menu_inbox")
async def callback_inbox(call: CallbackQuery):
    key_data = await get_key(call.from_user.id)
    if not key_data:
        await call.answer("You are not logged in.", show_alert=True)
        return
        
    api = NetlazyAPI(key_data["user_id"], key_data["private_pem"])
    try:
        inbox_items = await api.get_inbox()
        pending_count = sum(1 for req in inbox_items if req['status'] == 'pending' and not req['is_sender'])
        match_count = sum(1 for req in inbox_items if req['status'] == 'accepted')
        
        response_text = (
            f"📥 **Your Inbox**\n\n"
            f"🔹 **Pending Requests:** {pending_count}\n"
            f"🤝 **Active Matches:** {match_count}\n\n"
            "Open the Web App to view details, accept/decline handshakes, and access shared contacts."
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🌐 Open Inbox in Web App", web_app=WebAppInfo(url=settings.web_app_url))
        builder.button(text="🔙 Back", callback_data="menu_main")
        builder.adjust(1)
        
        await call.message.edit_text(response_text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except httpx.RequestError:
        await call.answer("Service waking up, try again in a few seconds.", show_alert=True)
    except Exception:
        await call.answer("Failed to load inbox.", show_alert=True)