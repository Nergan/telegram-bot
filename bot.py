import logging
import asyncio
import time
from aiogram import Bot, Dispatcher, types, BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

logger = logging.getLogger(__name__)

dp = Dispatcher()
bot_instance = None

# In-Memory Cache to rate-limit user profile DB upserts
# Format: {user_id: timestamp_of_last_update}
USER_UPDATE_CACHE = {}
USER_UPDATE_COOLDOWN = 3600  # Only update user profile once per hour per user

# Secure reference store for fire-and-forget tasks (prevents Python GC from killing them)
_bg_tasks = set()

def get_bot(token: str) -> Bot:
    """Singleton getter configured for standard long polling."""
    global bot_instance
    if not bot_instance:
        bot_instance = Bot(
            token=token, 
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        logger.info("Telegram Bot initialized with standard polling.")
    return bot_instance

class DatabaseMiddleware(BaseMiddleware):
    """Injects the database into handlers dynamically."""
    def __init__(self, db):
        self.db = db
        super().__init__()

    async def __call__(self, handler, event, data):
        data['db'] = self.db
        return await handler(event, data)

def fire_and_forget(coro):
    """Safely executes an async task in the background without blocking the main thread."""
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)

def extract_message_data(message: types.Message):
    """Returns: (text_content, content_type, file_unique_id)"""
    if message.text:
        return message.text, "text", None
    
    # Telegram sends multiple sizes for photos, the last one is the highest quality
    if message.photo:
        return "[photo]", "photo", message.photo[-1].file_unique_id
    if message.video:
        return "[video]", "video", message.video.file_unique_id
    if message.document:
        return "[document]", "document", message.document.file_unique_id
    if message.voice:
        return "[voice]", "voice", message.voice.file_unique_id
    if message.sticker:
        return "[sticker]", "sticker", message.sticker.file_unique_id
    
    return f"[{message.content_type}]", message.content_type, None

def get_user_data(user: types.User):
    """Extracts all standard available profile data."""
    return {
        "user_id": user.id,
        "is_bot": user.is_bot,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": user.language_code,
        "is_premium": user.is_premium,
    }

def should_update_user_db(user_id: int) -> bool:
    """Uses a simple local dictionary cache to check if we should update DB."""
    current_time = time.monotonic()
    last_updated = USER_UPDATE_CACHE.get(user_id, 0)
    
    if current_time - last_updated > USER_UPDATE_COOLDOWN:
        USER_UPDATE_CACHE[user_id] = current_time
        return True
    return False

async def background_log_message(db, user_id: int, msg_type: str, text: str, date, file_unique_id: str, direction: str):
    """Logs the message to MongoDB asynchronously."""
    try:
        await db.chat_logs.insert_one({
            "user_id": user_id,
            "direction": direction,
            "type": msg_type,
            "text": text,
            "file_unique_id": file_unique_id,
            "date": date
        })
    except Exception as e:
        logger.error(f"Failed to log {direction} message: {e}")

async def background_update_user(db, user: types.User):
    """Updates user metadata to MongoDB asynchronously."""
    if not should_update_user_db(user.id):
        return

    update_doc = {"$set": get_user_data(user)}
    if user.username:
        update_doc["$addToSet"] = {"usernames": user.username}

    try:
        await db.users.update_one({"user_id": user.id}, update_doc, upsert=True)
    except Exception as e:
        logger.error(f"Failed to update user profile: {e}")
        # Reset cache so it tries again next time
        USER_UPDATE_CACHE.pop(user.id, None)

@dp.message()
async def process_message(message: types.Message, db):
    if message.from_user.is_bot:
        return
        
    text, msg_type, file_unique_id = extract_message_data(message)
    
    # 1. Fire-and-forget DB Operations (Non-Blocking)
    fire_and_forget(background_update_user(db, message.from_user))
    fire_and_forget(background_log_message(
        db, message.from_user.id, msg_type, text, message.date, file_unique_id, "incoming"
    ))

    try:
        # 2. Echo behaviour (modified to acknowledge non-text)
        reply_text = text if msg_type == "text" else f"Received your {msg_type}!"
        sent_message = await message.answer(reply_text)

        # 3. Log the outgoing reply in the background
        fire_and_forget(background_log_message(
            db, message.from_user.id, "text", sent_message.text, sent_message.date, None, "outgoing"
        ))
    except Exception as e:
        logger.error(f"Telegram Bot Worker Error: {e}", exc_info=True)