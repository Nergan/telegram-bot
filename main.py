import random
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from aiogram import Dispatcher
from aiogram.types import Update

from infrastructure.config import WEBHOOK_URL, WEBHOOK_SECRET, MONGODB_URI
from infrastructure.database.mongo_repository import (
    MongoDatabase, MongoUserRepository, MongoProfileRepository, 
    MongoContactRequestRepository, MongoTagRepository
)
from infrastructure.bot.storage import MongoFSMStorage
from application.services import (
    UserService, ProfileService, BrowseService, 
    ContactRequestService, TagService
)
from bot.bot_setup import bot, setup_bot_commands
from bot.middlewares import AdvancedMiddleware
from bot.handlers import router as bot_router
from webapp.api import router as webapp_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Repositories and Services globally
mongo_db = MongoDatabase(MONGODB_URI)
user_repo = MongoUserRepository(mongo_db)
profile_repo = MongoProfileRepository(mongo_db)
req_repo = MongoContactRequestRepository(mongo_db)
tag_repo = MongoTagRepository(mongo_db)

user_service = UserService(user_repo)
profile_service = ProfileService(profile_repo)
browse_service = BrowseService(profile_repo, user_repo)
contact_req_service = ContactRequestService(req_repo)
tag_service = TagService(tag_repo)

# Initialize Aiogram Dispatcher with Dependency Injection
dp = Dispatcher(
    storage=MongoFSMStorage(mongo_db),
    mongo_db=mongo_db,
    user_service=user_service,
    profile_service=profile_service,
    browse_service=browse_service,
    contact_req_service=contact_req_service,
    tag_service=tag_service
)
dp.update.middleware(AdvancedMiddleware())
dp.include_router(bot_router)

bg_tasks = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Prepare Database & Indexes
    await mongo_db.setup_indexes()
    
    # Async migration for existing profiles missing random_index
    docs = await profile_repo.get_all_missing_random_index()
    for d in docs:
        await profile_repo.update_by_id(d["_id"], {"random_index": random.random()})
        
    # Start log batching worker
    app.state.log_task = asyncio.create_task(mongo_db.log_worker())
    
    await setup_bot_commands()
    
    webhook_url = f"{WEBHOOK_URL}/webhook/{WEBHOOK_SECRET}"
    await bot.set_webhook(
        url=webhook_url, 
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"]
    )
    logger.info("Webhook registered.")
    
    yield
    
    logger.info("Shutdown signal received.")
    if bg_tasks:
        logger.info(f"Awaiting {len(bg_tasks)} background webhook tasks...")
        await asyncio.gather(*bg_tasks, return_exceptions=True)
        
    if app.state.log_task:
        app.state.log_task.cancel()
        try:
            await app.state.log_task
        except asyncio.CancelledError:
            pass
            
    await bot.session.close()
    mongo_db.close()
    logger.info("Shutdown complete.")

app = FastAPI(lifespan=lifespan)

# Inject services into FastAPI's Application State
app.state.user_service = user_service
app.state.profile_service = profile_service
app.state.tag_service = tag_service
app.state.contact_req_service = contact_req_service

app.include_router(webapp_router)

@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok"}

def _on_task_done(task: asyncio.Task):
    bg_tasks.discard(task)
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Background webhook task failed: {e}", exc_info=True)

@app.post("/webhook/{secret}")
async def bot_webhook(secret: str, request: Request):
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403)
        
    update_data = await request.json()
    update = Update.model_validate(update_data, context={"bot": bot})
    
    task = asyncio.create_task(dp.feed_update(bot, update))
    bg_tasks.add(task)
    task.add_done_callback(_on_task_done)
    
    return {"ok": True}