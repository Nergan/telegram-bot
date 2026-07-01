import os
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from bot import get_bot, dp, DatabaseMiddleware

logger = logging.getLogger(__name__)

# State container to persist resources across the Lifespan
class AppState:
    db_client = None
    polling_task = None

async def run_bot_polling(token):
    """Wrapper task to GUARANTEE exceptions are logged and not swallowed."""
    try:
        bot = get_bot(token)
        # Clear stuck webhooks before Long Polling
        await bot.delete_webhook(drop_pending_updates=True)
        # Start polling cleanly
        await dp.start_polling(bot, handle_signals=False)
    except asyncio.CancelledError:
        logger.info("Bot polling cancelled.")
    except Exception as e:
        logger.error(f"FATAL BOT POLLING ERROR: {e}", exc_info=True)

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """FastAPI >= 0.100.0 Lifespan management for DB and Bot."""
    load_dotenv()
    
    token = os.getenv("TOKEN")
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    
    if not token:
        logger.warning("Telegram Bot skipped: No TOKEN found in environment.")
        yield
        return

    # 1. Initialize DB
    AppState.db_client = AsyncIOMotorClient(mongodb_uri, tls=True, tlsAllowInvalidCertificates=True)
    db = AppState.db_client["bot"]
    
    # 2. Bind DB to Aiogram via Middleware
    dp.message.middleware(DatabaseMiddleware(db))
    
    # 3. Start Polling safely in background
    AppState.polling_task = asyncio.create_task(run_bot_polling(token))
    logger.info("Telegram Bot Plugin initialized: Long Polling active.")
    
    # App runs while execution is yielded
    yield 
    
    # --- Shutdown Phase ---
    logger.info("Shutting down Telegram Bot Plugin...")
    if token:
        bot = get_bot(token)
        if bot:
            await bot.session.close()
            
    if AppState.polling_task:
        AppState.polling_task.cancel()
        
    if AppState.db_client:
        AppState.db_client.close()

# Initialize FastAPI with the Lifespan
app = FastAPI(title="Telegram Bot", lifespan=app_lifespan) 
router = APIRouter()

@router.get("/", summary="Redirects to Bot")
async def redirect_to_bot():
    return RedirectResponse(url="https://t.me/hornychat42_bot")

app.include_router(router)