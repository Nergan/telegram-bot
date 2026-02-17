from datetime import datetime
from os import getenv

from dotenv import load_dotenv
from llama_cpp import Llama
from motor.motor_asyncio import AsyncIOMotorClient

from config import N_CTX, TEMPARETURE, MAX_TOKENS, MODEL_PATH, STARTER_PROMPT_PATH


load_dotenv()

MONGO_URL = getenv("MONGODB_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)
db = client["bot"]
users_collection = db["users"]

model = Llama(
    model_path=MODEL_PATH,
    n_ctx=N_CTX,
    verbose=False,
    temperature=TEMPARETURE
)


def get_starter_prompt(filename=STARTER_PROMPT_PATH):
    with open(filename, encoding='utf-8') as file:
        starter_prompt = f'{file.read().encode('utf-8').decode('unicode_escape')}\n\n'
    return starter_prompt


async def get_history(msg):
    user_id = str(msg.from_user.id)
    username = msg.from_user.username
    doc = await users_collection.find_one({"user_id": user_id, "username": username})
    if doc:
        return ''.join(doc.get('history', []))
    return ''


async def get_tokens(msg, model=model):
    history = await get_history(msg)
    return len(model.tokenize(history.encode("utf-8"), add_bos=False))


async def get_user_alias(msg):
    user_id = str(msg.from_user.id)
    username = msg.from_user.username
    doc = await users_collection.find_one({"user_id": user_id, "username": username})
    if doc:
        return doc.get('user_alias', msg.from_user.first_name)
    return msg.from_user.first_name


async def get_bot_alias(msg):
    user_id = str(msg.from_user.id)
    username = msg.from_user.username
    doc = await users_collection.find_one({"user_id": user_id, "username": username})
    if doc:
        return doc.get('bot_alias', 'Mistress')
    return 'Mistress'


async def upd_names(msg, bot_new, user_new):
    user_id = str(msg.from_user.id)
    username = msg.from_user.username
    doc = await users_collection.find_one({"user_id": user_id, "username": username})
    if not doc:
        return
    bot_old = doc['bot_alias']
    user_old = doc['user_alias']
    history = doc['history']

    if history:
        history[0] = history[0].replace(bot_old, bot_new).replace(user_old, user_new)

    for i, story in enumerate(history[1:], start=1):
        if f'{bot_old}: ' in story:
            history[i] = story.replace(f'{bot_old}: ', f'{bot_new}: ')
        elif f'{user_old}: ' in story:
            history[i] = story.replace(f'{user_old}: ', f'{user_new}: ')

    await users_collection.update_one(
        {"user_id": user_id, "username": username},
        {"$set": {"user_alias": user_new, "bot_alias": bot_new, "history": history}}
    )


async def trim_history(msg, model=model):
    limit = model.n_ctx() - MAX_TOKENS
    tokens = await get_tokens(msg, model)
    if tokens <= limit:
        return

    user_id = str(msg.from_user.id)
    username = msg.from_user.username
    doc = await users_collection.find_one({"user_id": user_id, "username": username})
    if not doc:
        return

    history = doc['history']
    new_history = [history[0]]

    for story in reversed(history[1:]):
        temp_history = new_history.copy()
        temp_history.insert(1, story)
        if len(model.tokenize(''.join(temp_history).encode("utf-8"), add_bos=False)) > limit:
            break
        new_history.insert(1, story)

    await users_collection.update_one(
        {"user_id": user_id, "username": username},
        {"$set": {"history": new_history}}
    )


async def add_history(msg, content, trim=True, model=model):
    user_id = str(msg.from_user.id)
    username = msg.from_user.username
    await users_collection.update_one(
        {"user_id": user_id, "username": username},
        {"$push": {"history": content}}
    )
    if trim:
        await trim_history(msg, model)


async def add_log(msg, role, content):
    user_id = str(msg.from_user.id)
    username = msg.from_user.username
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'role': role,
        'content': content
    }
    await users_collection.update_one(
        {"user_id": user_id, "username": username},
        {"$push": {"log": log_entry}}
    )


async def add_data(msg, role, content):
    user_id = str(msg.from_user.id)
    username = msg.from_user.username

    doc = await users_collection.find_one({"user_id": user_id, "username": username})
    if not doc:
        # Создаём пользователя с плейсхолдерами
        user_alias_placeholder = '<user alias>'
        bot_alias_placeholder = '<bot alias>'
        starter = get_starter_prompt()
        history = [starter]
        log = []
        await users_collection.insert_one({
            "user_id": user_id,
            "username": username,
            "user_alias": user_alias_placeholder,
            "bot_alias": bot_alias_placeholder,
            "history": history,
            "log": log
        })
        # Заменяем плейсхолдеры на реальные имена
        real_user_alias = msg.from_user.first_name
        real_bot_alias = 'Mistress'
        await upd_names(msg, real_bot_alias, real_user_alias)

    await add_log(msg, role, content)
    if role in {'user', 'bot'}:
        await add_history(msg, content)


async def clear_history(msg):
    user_id = str(msg.from_user.id)
    username = msg.from_user.username
    doc = await users_collection.find_one({"user_id": user_id, "username": username})
    if doc and doc['history']:
        new_history = [doc['history'][0]]
        await users_collection.update_one(
            {"user_id": user_id, "username": username},
            {"$set": {"history": new_history}}
        )