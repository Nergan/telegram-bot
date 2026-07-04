import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dating_bot_secure_path_abc123")

BOT_COMMANDS = [
    ("start", "Start or restart the bot"),
    ("help", "Help information"),
    ("lang_en", "Set English"),
    ("lang_ru", "Set Russian")
]

# Advanced Tags Dictionary (Multi-language Support)
AVAILABLE_TAGS = [
    {"id": "python", "display": {"en": "Python", "ru": "Python"}, "aliases": {"en": ["coding", "programming", "dev", "it", "developer"], "ru": ["код", "программирование", "айти", "разработка"]}},
    {"id": "art", "display": {"en": "Art", "ru": "Искусство"}, "aliases": {"en": ["drawing", "painting", "creative", "design"], "ru": ["рисунок", "творчество", "дизайн", "рисование"]}},
    {"id": "music", "display": {"en": "Music", "ru": "Музыка"}, "aliases": {"en": ["audio", "instruments", "singing", "band"], "ru": ["аудио", "инструменты", "пение", "группа"]}},
    {"id": "gaming", "display": {"en": "Gaming", "ru": "Игры"}, "aliases": {"en": ["games", "videogames", "esports", "play"], "ru": ["видеоигры", "киберспорт", "играть"]}},
    {"id": "fitness", "display": {"en": "Fitness", "ru": "Фитнес"}, "aliases": {"en": ["gym", "workout", "health", "exercise"], "ru": ["спортзал", "тренировка", "здоровье", "спорт"]}},
    {"id": "moscow", "display": {"en": "Moscow", "ru": "Москва"}, "aliases": {"en": ["russia", "msk"], "ru": ["россия", "мск"]}},
    {"id": "new_york", "display": {"en": "New York", "ru": "Нью-Йорк"}, "aliases": {"en": ["ny", "nyc", "usa", "america"], "ru": ["нью-йорк", "сша", "америка"]}},
    {"id": "introvert", "display": {"en": "Introvert", "ru": "Интроверт"}, "aliases": {"en": ["quiet", "shy", "homebody"], "ru": ["тихий", "скромный", "домосед"]}},
    {"id": "extrovert", "display": {"en": "Extrovert", "ru": "Экстраверт"}, "aliases": {"en": ["outgoing", "social", "party"], "ru": ["общительный", "социальный", "вечеринка"]}},
    {"id": "female", "display": {"en": "Female", "ru": "Девушка"}, "aliases": {"en": ["woman", "girl"], "ru": ["женщина", "девочка"]}},
    {"id": "male", "display": {"en": "Male", "ru": "Парень"}, "aliases": {"en": ["man", "boy"], "ru": ["мужчина", "мальчик"]}},
]