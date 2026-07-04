import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from aiogram.types import Update

from core.config import WEBHOOK_URL, WEBHOOK_SECRET
from core.database import Database
from bot.bot_setup import bot, dp, setup_bot_commands
from bot.middlewares import AdvancedMiddleware
from bot.handlers import router as bot_router
from webapp.api import router as webapp_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Apply Middleware and Router
dp.update.middleware(AdvancedMiddleware())
dp.include_router(bot_router)

# Task tracker for graceful shutdown
bg_tasks = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Await the async connection and index setup
    await Database.connect()
    
    # Start log batching worker
    Database.log_task = asyncio.create_task(Database.log_worker())
    
    # Async migration for existing profiles missing random_index
    await Database.migrate_random_indexes()
    
    await setup_bot_commands()
    
    webhook_url = f"{WEBHOOK_URL}/webhook/{WEBHOOK_SECRET}"
    await bot.set_webhook(
        url=webhook_url, 
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )
    logger.info("Webhook registered.")
    
    yield
    
    # Graceful Shutdown
    logger.info("Shutdown signal received.")
    if bg_tasks:
        logger.info(f"Awaiting {len(bg_tasks)} background webhook tasks...")
        await asyncio.gather(*bg_tasks, return_exceptions=True)
        
    if Database.log_task:
        Database.log_task.cancel()
        try:
            await Database.log_task
        except asyncio.CancelledError:
            pass
            
    await bot.session.close()
    Database.disconnect()
    logger.info("Shutdown complete.")

app = FastAPI(lifespan=lifespan)
app.include_router(webapp_router)

@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok"}

# Helper to prevent silent task failures
def _on_task_done(task: asyncio.Task):
    bg_tasks.discard(task)
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Background webhook task failed: {e}", exc_info=True)

@app.post("/webhook/{secret}")
async def bot_webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403)
        
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    
    # Send to task tracker to ensure completion before SIGTERM
    task = asyncio.create_task(dp.feed_update(bot, update))
    bg_tasks.add(task)
    
    # Attach safety callback
    task.add_done_callback(_on_task_done)
    
    return {"ok": True}