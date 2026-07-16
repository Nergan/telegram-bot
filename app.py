import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import settings
from handlers import router as main_router
from vault import init_vault

async def on_startup(bot: Bot):
    await init_vault()
    webhook_url = settings.resolved_webhook_url
    if not webhook_url:
        logging.warning("Webhook URL is empty. Must set WEBHOOK_BASE_URL or RENDER_EXTERNAL_URL.")
        return
        
    formatted_webhook = f"{webhook_url.rstrip('/')}/webhook"
    await bot.set_webhook(formatted_webhook)
    logging.info(f"Webhook configured at: {formatted_webhook}")

async def health_check(request):
    return web.Response(text="OK", status=200)

def setup_bot_app():
    # Setup AIOHTTP web application
    app = web.Application()
    app.router.add_get("/health", health_check)

    # Graceful fallback if secrets are missing during Render build phase
    if not settings.telegram_bot_token:
        logging.error("TELEGRAM_BOT_TOKEN is missing! Starting dummy web server for Render health checks.")
        return app

    # Setup Aiogram Bot and Dispatcher
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(main_router)
    dp.startup.register(on_startup)

    # Create the webhook request handler
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path="/webhook")
    
    # Mount the Aiogram handler to the web app
    setup_application(app, dp, bot=bot)
    
    return app

app = setup_bot_app()