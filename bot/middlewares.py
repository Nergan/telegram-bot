from aiogram import BaseMiddleware
from aiogram.types import Update
from core.database import Database

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        user_id = None
        action_type = "unknown"
        log_data = {}

        if event.message:
            user_id = event.message.from_user.id
            action_type = "message"
            log_data = {"text": event.message.text, "content_type": event.message.content_type}
            if event.message.text and event.message.text.startswith("/"):
                action_type = "command"
        elif event.callback_query:
            user_id = event.callback_query.from_user.id
            action_type = "callback_query"
            log_data = {"data": event.callback_query.data}
        
        if user_id:
            # Fire and forget logging
            import asyncio
            asyncio.create_task(Database.log_action(user_id, action_type, log_data))
            
        return await handler(event, data)