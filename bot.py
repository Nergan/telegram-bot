import logging
import asyncio
import time
from aiogram import Bot, Dispatcher, types, BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

logger = logging.getLogger(__name__)

dp = Dispatcher()
bot_instance = None

USER_UPDATE_CACHE = {}
USER_UPDATE_COOLDOWN = 3600  
_bg_tasks = set()

def get_bot(token: str) -> Bot:
    global bot_instance
    if not bot_instance:
        bot_instance = Bot(
            token=token, 
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        logger.info("Telegram Bot initialized with standard polling.")
    return bot_instance

class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, db):
        self.db = db
        super().__init__()

    async def __call__(self, handler, event, data):
        data['db'] = self.db
        return await handler(event, data)

def fire_and_forget(coro):
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)

def extract_message_data(message: types.Message):
    """
    Extracts text/captions and both identifiers.
    Returns: (text_content, content_type, file_unique_id, file_id)
    """
    text_content = message.text or message.caption

    if message.photo:
        best = message.photo[-1]
        return text_content or "[photo]", "photo", best.file_unique_id, best.file_id
    if message.video:
        return text_content or "[video]", "video", message.video.file_unique_id, message.video.file_id
    if message.video_note:
        return text_content or "[video_note]", "video_note", message.video_note.file_unique_id, message.video_note.file_id
    if message.animation:
        return text_content or "[animation]", "animation", message.animation.file_unique_id, message.animation.file_id
    if message.audio:
        return text_content or "[audio]", "audio", message.audio.file_unique_id, message.audio.file_id
    if message.document:
        return text_content or "[document]", "document", message.document.file_unique_id, message.document.file_id
    if message.voice:
        return text_content or "[voice]", "voice", message.voice.file_unique_id, message.voice.file_id
    if message.sticker:
        return text_content or "[sticker]", "sticker", message.sticker.file_unique_id, message.sticker.file_id
    
    if message.text:
        return message.text, "text", None, None
        
    return f"[{message.content_type}]", message.content_type, None, Nonene

def get_user_data(user: types.User):
    return {
        "user_id": user.id,
        "is_bot": user.is_bot,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": user.language_code,
        "is_premium": user.is_premium,
    }

def should_update_user_db(user_id: int) -> bool:
    current_time = time.monotonic()
    last_updated = USER_UPDATE_CACHE.get(user_id, 0)
    
    if current_time - last_updated > USER_UPDATE_COOLDOWN:
        USER_UPDATE_CACHE[user_id] = current_time
        return True
    return False

async def background_log_message(db, user_id: int, msg_type: str, text: str, date, file_unique_id: str, file_id: str, direction: str):
    """Logs the message, including both file identifiers."""
    try:
        await db.chat_logs.insert_one({
            "user_id": user_id,
            "direction": direction,
            "type": msg_type,
            "text": text,
            "file_unique_id": file_unique_id,
            "file_id": file_id,
            "date": date
        })
    except Exception as e:
        logger.error(f"Failed to log {direction} message: {e}")

async def background_update_user(db, user: types.User):
    if not should_update_user_db(user.id):
        return

    update_doc = {"$set": get_user_data(user)}
    if user.username:
        update_doc["$addToSet"] = {"usernames": user.username}

    try:
        await db.users.update_one({"user_id": user.id}, update_doc, upsert=True)
    except Exception as e:
        logger.error(f"Failed to update user profile: {e}")
        USER_UPDATE_CACHE.pop(user.id, None)

@dp.message()
async def process_message(message: types.Message, db):
    if message.from_user.is_bot:
        return
        
    text, msg_type, file_unique_id, file_id = extract_message_data(message)
    
    fire_and_forget(background_update_user(db, message.from_user))
    fire_and_forget(background_log_message(
        db, message.from_user.id, msg_type, text, message.date, file_unique_id, file_id, "incoming"
    ))

    try:
        sent_message = None
        if msg_type == "text":
            sent_message = await message.answer(text)
        elif msg_type == "photo":
            sent_message = await message.answer_photo(photo=file_id, caption=message.caption)
        elif msg_type == "video":
            sent_message = await message.answer_video(video=file_id, caption=message.caption)
        elif msg_type == "video_note":
            # Video notes do not support captions
            sent_message = await message.answer_video_note(video_note=file_id)
        elif msg_type == "animation":
            sent_message = await message.answer_animation(animation=file_id, caption=message.caption)
        elif msg_type == "audio":
            sent_message = await message.answer_audio(audio=file_id, caption=message.caption)
        elif msg_type == "document":
            sent_message = await message.answer_document(document=file_id, caption=message.caption)
        elif msg_type == "voice":
            sent_message = await message.answer_voice(voice=file_id, caption=message.caption)
        elif msg_type == "sticker":
            sent_message = await message.answer_sticker(sticker=file_id)
        else:
            sent_message = await message.answer(f"Received an unsupported media type: {msg_type}")

        if sent_message:
            out_text, out_type, out_unique_id, out_file_id = extract_message_data(sent_message)
            fire_and_forget(background_log_message(
                db, message.from_user.id, out_type, out_text, sent_message.date, out_unique_id, out_file_id, "outgoing"
            ))
            
    except Exception as e:
        logger.error(f"Telegram Bot Worker Error: {e}", exc_info=True)