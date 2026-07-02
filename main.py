import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from aiogram.types import Update

from core.config import WEBHOOK_URL, TOKEN  # WEBHOOK_PATH больше не нужен
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
    
    # 2. Setup Webhook (в Telegram передаем полный URL с токеном)
    webhook_url = f"{WEBHOOK_URL}/webhook/{TOKEN}"
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

@app.get("/")
async def health_check():
    """Корневой эндпоинт для проверок работоспособности (Render Health Checks)"""
    return {"status": "ok", "message": "Telegram Bot is running"}

@app.post("/webhook/{token}")
async def bot_webhook(token: str, request: Request):
    """
    Эндпоинт для получения обновлений от Telegram.
    Использование параметра {token} защищает от проблем с парсингом двоеточия.
    """
    if token != TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
        
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}