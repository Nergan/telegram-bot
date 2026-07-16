import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
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
    
    # Push command menu natively to Telegram UI
    await bot.set_my_commands([
        BotCommand(command="start", description="Open main menu"),
        BotCommand(command="help", description="Show help info"),
        BotCommand(command="language", description="Change bot language"),
    ])
    logging.info(f"Webhook configured at: {formatted_webhook}")

async def health_check(request):
    return web.Response(text="OK", status=200)

def setup_bot_app():
    # Setup AIOHTTP web application
    app = web.Application()
    app.router.add_get("/health", health_check)

    if not settings.telegram_bot_token:
        logging.error("TELEGRAM_BOT_TOKEN is missing! Starting dummy web server for Render health checks.")
        return app

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(main_router)
    dp.startup.register(on_startup)

    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path="/webhook")
    
    setup_application(app, dp, bot=bot)
    
    return app

app = setup_bot_app()