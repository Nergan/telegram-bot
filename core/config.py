import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Секретная строка для безопасного пути вебхука (скроет токен в логах POST-запросов).
# Рекомендуется задать её в переменных окружения Render (например, случайный набор букв и цифр).
# Если переменная не задана на Render, используется дефолтное безопасное значение ниже.
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dating_bot_secure_path_abc123")

# Pre-defined Tags
AVAILABLE_TAGS = [
    "art", "music", "tech", "python", "gaming", "fitness", 
    "travel", "movies", "photography", "cooking", "sports",
    "female", "male", "chubby", "fit", "introvert", "extrovert",
    "moscow", "kazakhstan", "london", "tokyo", "new_york"
]