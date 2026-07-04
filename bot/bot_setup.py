from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from core.config import TOKEN, BOT_COMMANDS
from core.storage import MongoStorage

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
# Bind the persistent storage to prevent state loss
dp = Dispatcher(storage=MongoStorage())

async def setup_bot_commands():
    commands = [BotCommand(command=cmd, description=desc) for cmd, desc in BOT_COMMANDS]
    await bot.set_my_commands(commands)