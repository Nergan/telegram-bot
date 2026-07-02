import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dating_bot_secure_path_abc123")

# Bot Commands
BOT_COMMANDS = [
    ("start", "Restart bot or deep-link to a profile"),
    ("menu", "Open main navigation menu"),
    ("browse", "Start browsing the profile pool"),
    ("profiles", "Manage your profiles"),
    ("search", "Find a profile by ID (e.g., /search a1b2c3d4)")
]

# Advanced Tags Dictionary
AVAILABLE_TAGS = [
    {"id": "python", "display": "Python", "aliases": ["coding", "programming", "dev", "it", "developer"]},
    {"id": "art", "display": "Art", "aliases": ["drawing", "painting", "creative", "design"]},
    {"id": "music", "display": "Music", "aliases": ["audio", "instruments", "singing", "band"]},
    {"id": "gaming", "display": "Gaming", "aliases": ["games", "videogames", "esports", "play"]},
    {"id": "fitness", "display": "Fitness", "aliases": ["gym", "workout", "health", "exercise"]},
    {"id": "moscow", "display": "Moscow", "aliases": ["russia", "msk"]},
    {"id": "new_york", "display": "New York", "aliases": ["ny", "nyc", "usa", "america"]},
    {"id": "introvert", "display": "Introvert", "aliases": ["quiet", "shy", "homebody"]},
    {"id": "extrovert", "display": "Extrovert", "aliases": ["outgoing", "social", "party"]},
    {"id": "female", "display": "Female", "aliases": ["woman", "girl"]},
    {"id": "male", "display": "Male", "aliases": ["man", "boy"]},
]