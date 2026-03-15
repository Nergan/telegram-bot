from os import getenv


TOKEN = getenv("TOKEN")
MONGODB_URI = getenv("MONGODB_URI")

N_CTX = 2048 # размер контекста
TEMPARETURE = 0.85 # степень отсебятины (от 0 до 1)
MAX_TOKENS = 128 # размер ответа

MODEL_PATH = getenv('MODEL_PATH')
STARTER_PROMPT_PATH = getenv('STARTER_PROMPT_PATH')