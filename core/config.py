import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dating_bot_secure_path_abc123")

DATA_SPEED_LIMIT = 0.3 # optimal - 0.8
KEYBOARD_SPEED_LIMIT = 0.2 # optimal - 0.5

BOT_COMMANDS = [
    ("start", "Start or restart the bot"),
    ("help", "Help information"),
    ("lang_en", "Set English"),
    ("lang_ru", "Set Russian"),
    ("lang_pt", "Set Portuguese (Brazil)")
]