from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from application.config import TOKEN, BOT_COMMANDS

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

async def setup_bot_commands():
    commands = [BotCommand(command=cmd, description=desc) for cmd, desc in BOT_COMMANDS]
    await bot.set_my_commands(commands)