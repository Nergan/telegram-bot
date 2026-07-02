import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from aiogram.types import Update

from core.config import WEBHOOK_URL, WEBHOOK_PATH, TOKEN
from core.database import Database
from bot.bot_setup import bot, dp
from bot.handlers import router as bot_router
from webapp.api import router as webapp_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dp.include_router(bot_router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Connect DB
    Database.connect()
    
    # 2. Setup Webhook
    webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    logger.info(f"Webhook set to {webhook_url}")
    
    yield
    
    # 3. Teardown
    await bot.delete_webhook()
    await bot.session.close()
    Database.disconnect()
    logger.info("Application shutdown complete.")

app = FastAPI(lifespan=lifespan)
app.include_router(webapp_router)

@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    """FastAPI endpoint to receive Telegram Updates"""
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

# Run locally using: uvicorn main:app --reload