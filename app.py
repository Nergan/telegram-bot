import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from .config import settings
from .handlers import router as main_router

async def on_startup(bot: Bot):
    webhook_url = f"{settings.webhook_base_url.rstrip('/')}/webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook configured at: {webhook_url}")

async def health_check(request):
    return web.Response(text="OK", status=200)

def setup_bot_app():
    # Setup Aiogram Bot and Dispatcher
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(main_router)
    dp.startup.register(on_startup)

    # Setup AIOHTTP web application
    app = web.Application()
    app.router.add_get("/health", health_check)

    # Create the webhook request handler
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path="/webhook")
    
    # Mount the Aiogram handler to the web app
    setup_application(app, dp, bot=bot)
    
    return app

app = setup_bot_app()