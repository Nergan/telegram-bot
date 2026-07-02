import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from aiogram.types import Update

from core.config import WEBHOOK_URL, TOKEN, WEBHOOK_SECRET  # Импортируем WEBHOOK_SECRET
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
    
    # 2. Setup Webhook (Используем секретную строку вместо токена в URL)
    webhook_url = f"{WEBHOOK_URL}/webhook/{WEBHOOK_SECRET}"
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    logger.info("Webhook successfully registered with a secure secret path.")
    
    yield
    
    # 3. Teardown
    await bot.session.close()
    Database.disconnect()
    logger.info("Application shutdown complete.")

app = FastAPI(lifespan=lifespan)
app.include_router(webapp_router)

@app.get("/")
@app.head("/")
async def root():
    """Эндпоинт для проверок работоспособности (Render Health Checks)"""
    return {"status": "ok", "message": "Bot is running"}

@app.post("/webhook/{secret}")
async def bot_webhook(secret: str, request: Request):
    """Принимаем обновления только по секретному пути, проверяя его на валидность"""
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
        
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}