import time
from aiogram import BaseMiddleware
from aiogram.types import Update
from core.database import Database

# In-memory throttle state (Very lightweight: ~10MB for 100k users)
THROTTLE_STORE = {}

class AdvancedMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        user_id = None
        action_type = None
        log_data = {}
        
        # Check FSM context
        state = data.get("state")
        is_fsm = False
        if state:
            is_fsm = await state.get_state() is not None

        if event.message:
            user_id = event.message.from_user.id
            
            # Message Throttling (0.8s)
            now = time.time()
            if now - THROTTLE_STORE.get(user_id, 0) < 0.8:
                return # Silently drop spam message
            THROTTLE_STORE[user_id] = now
            
            if event.message.text and event.message.text.startswith("/"):
                action_type = "cmd"
                log_data = {"txt": event.message.text[:50]} # Truncated
            elif is_fsm:
                action_type = "fsm_msg"
            else:
                action_type = "msg"
                
        elif event.callback_query:
            user_id = event.callback_query.from_user.id
            
            # Callback Throttling (0.5s)
            now = time.time()
            if now - THROTTLE_STORE.get(user_id, 0) < 0.5:
                return await event.callback_query.answer()
            THROTTLE_STORE[user_id] = now
            
            action_type = "cb"
            log_data = {"dt": event.callback_query.data[:30]} # Truncated
        
        lang = "en"
        if user_id:
            lang = await Database.get_user_lang(user_id)
            
            # Log Volume Reduction: Log ONLY commands, callbacks, and FSM inputs
            if action_type in ["cmd", "cb", "fsm_msg"]:
                Database.log_action_queued(user_id, action_type, log_data)
            
        data["lang"] = lang
        return await handler(event, data)