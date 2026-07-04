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
    ("lang_ru", "Set Russian"),
    ("lang_pt", "Set Portuguese (Brazil)")
]

# Advanced Tags Dictionary (Multi-language Support)
AVAILABLE_TAGS = [
    {"id": "python", "display": {"en": "Python", "ru": "Python", "pt": "Python"}, "aliases": {"en": ["coding", "programming", "dev", "it", "developer"], "ru": ["код", "программирование", "айти", "разработка"], "pt": ["programação", "desenvolvimento", "ti", "dev", "codigo", "programar"]}},
    {"id": "art", "display": {"en": "Art", "ru": "Искусство", "pt": "Arte"}, "aliases": {"en": ["drawing", "painting", "creative", "design"], "ru": ["рисунок", "творчество", "дизайн", "рисование"], "pt": ["desenho", "pintura", "criatividade", "design", "ilustracao"]}},
    {"id": "music", "display": {"en": "Music", "ru": "Музыка", "pt": "Música"}, "aliases": {"en": ["audio", "instruments", "singing", "band"], "ru": ["аудио", "инструменты", "пение", "группа"], "pt": ["audio", "instrumentos", "canto", "banda", "tocar"]}},
    {"id": "gaming", "display": {"en": "Gaming", "ru": "Игры", "pt": "Jogos"}, "aliases": {"en": ["games", "videogames", "esports", "play"], "ru": ["видеоигры", "киберспорт", "играть"], "pt": ["games", "videogames", "esports", "jogar", "play"]}},
    {"id": "fitness", "display": {"en": "Fitness", "ru": "Фитнес", "pt": "Fitness"}, "aliases": {"en": ["gym", "workout", "health", "exercise"], "ru": ["спортзал", "тренировка", "здоровье", "спорт"], "pt": ["academia", "treino", "saude", "exercicio", "esporte"]}},
    {"id": "moscow", "display": {"en": "Moscow", "ru": "Москва", "pt": "Moscou"}, "aliases": {"en": ["russia", "msk"], "ru": ["россия", "мск"], "pt": ["russia", "moscou"]}},
    {"id": "new_york", "display": {"en": "New York", "ru": "Нью-Йорк", "pt": "Nova York"}, "aliases": {"en": ["ny", "nyc", "usa", "america"], "ru": ["нью-йорк", "сша", "америка"], "pt": ["ny", "nyc", "eua", "america"]}},
    {"id": "introvert", "display": {"en": "Introvert", "ru": "Интроверт", "pt": "Introvertido"}, "aliases": {"en": ["quiet", "shy", "homebody"], "ru": ["тихий", "скромный", "домосед"], "pt": ["quieto", "timido", "caseiro", "reservado"]}},
    {"id": "extrovert", "display": {"en": "Extrovert", "ru": "Экстраверт", "pt": "Extrovertido"}, "aliases": {"en": ["outgoing", "social", "party"], "ru": ["общительный", "социальный", "вечеринка"], "pt": ["comunicativo", "social", "festa", "extrovertida"]}},
    {"id": "female", "display": {"en": "Female", "ru": "Девушка", "pt": "Feminino"}, "aliases": {"en": ["woman", "girl"], "ru": ["женщина", "девочка"], "pt": ["mulher", "garota", "feminino", "moca"]}},
    {"id": "male", "display": {"en": "Male", "ru": "Парень", "pt": "Masculino"}, "aliases": {"en": ["man", "boy"], "ru": ["мужчина", "мальчик"], "pt": ["homem", "garoto", "masculino", "rapaz"]}},
]