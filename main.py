import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from aiogram.types import Update

from core.config import WEBHOOK_URL, WEBHOOK_SECRET
from core.database import Database
from bot.bot_setup import bot, dp, setup_bot_commands
from bot.middlewares import LoggingMiddleware
from bot.handlers import router as bot_router
from webapp.api import router as webapp_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Apply Middleware and Router
dp.update.middleware(LoggingMiddleware())
dp.include_router(bot_router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Database.connect()
    await setup_bot_commands()
    
    webhook_url = f"{WEBHOOK_URL}/webhook/{WEBHOOK_SECRET}"
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    logger.info("Webhook registered and commands updated.")
    
    yield
    
    await bot.session.close()
    Database.disconnect()
    logger.info("Application shutdown complete.")

app = FastAPI(lifespan=lifespan)
app.include_router(webapp_router)

@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok", "message": "Bot is running"}

@app.post("/webhook/{secret}")
async def bot_webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
        
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}