import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = f"/webhook/{TOKEN}"

# Pre-defined Tags
AVAILABLE_TAGS = [
    "art", "music", "tech", "python", "gaming", "fitness", 
    "travel", "movies", "photography", "cooking", "sports",
    "female", "male", "chubby", "fit", "introvert", "extrovert",
    "moscow", "kazakhstan", "london", "tokyo", "new_york"
]