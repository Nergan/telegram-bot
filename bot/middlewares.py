import time
from aiogram import BaseMiddleware
from aiogram.types import Update
from application.services import UserService
from application.locales import _
from application.config import DATA_SPEED_LIMIT, KEYBOARD_SPEED_LIMIT

THROTTLE_STORE = {}

class AdvancedMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        user_id = None
        action_type = None
        log_data = {}
        
        state = data.get("state")
        is_fsm = await state.get_state() is not None if state else False

        if event.message:
            user_id = event.message.from_user.id
            now = time.time()
            is_media_group = event.message.media_group_id is not None
            if not is_media_group and (now - THROTTLE_STORE.get(user_id, 0) < DATA_SPEED_LIMIT):
                return
            
            THROTTLE_STORE[user_id] = now
            
            if event.message.text and event.message.text.startswith("/"):
                action_type = "cmd"
                log_data = {"txt": event.message.text[:50]}
            elif is_fsm:
                action_type = "fsm_msg"
            else:
                action_type = "msg"
                
        elif event.callback_query:
            user_id = event.callback_query.from_user.id
            now = time.time()
            if now - THROTTLE_STORE.get(user_id, 0) < KEYBOARD_SPEED_LIMIT:
                return await event.callback_query.answer()
            THROTTLE_STORE[user_id] = now
            
            action_type = "cb"
            log_data = {"dt": event.callback_query.data[:30]}
        
        lang = "en"
        if user_id:
            user_service: UserService = data.get("user_service")
            lang = await user_service.get_lang(user_id)
            
            if await user_service.is_banned(user_id):
                if event.message:
                    await event.message.answer(_("err_banned", lang))
                elif event.callback_query:
                    await event.callback_query.answer(_("err_banned", lang), show_alert=True)
                return
            
            if action_type in ["cmd", "cb", "fsm_msg"]:
                user_service.log_action(user_id, action_type, log_data)
            
        data["lang"] = lang
        return await handler(event, data)