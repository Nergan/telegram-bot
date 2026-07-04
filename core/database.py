# At the top of core/database.py
from motor.motor_asyncio import AsyncIOMotorClient
import uuid
import datetime
import random
import asyncio
from core.config import MONGODB_URI
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None
    log_queue = None
    log_task = None

    @classmethod
    def connect(cls):
        cls.client = AsyncIOMotorClient(MONGODB_URI, tls=True, tlsAllowInvalidCertificates=True)
        cls.db = cls.client["day_dating_bot"]
        cls.log_queue = asyncio.Queue()
        # Build index for the O(log N) randomizer
        asyncio.create_task(cls.db.profiles.create_index([("random_index", 1)]))
        logger.info("Connected to MongoDB.")

    # ... keep disconnect ...

    @classmethod
    async def migrate_random_indexes(cls):
        """Populate missing indexes on restart for pre-existing users."""
        docs = await cls.db.profiles.find({"random_index": {"$exists": False}}).to_list(None)
        for d in docs:
            await cls.db.profiles.update_one({"_id": d["_id"]}, {"$set": {"random_index": random.random()}})

    @classmethod
    async def log_worker(cls):
        """Background worker that flushes the queue to the database in batches."""
        while True:
            try:
                batch = []
                item = await cls.log_queue.get()
                batch.append(item)
                
                while len(batch) < 50:
                    try:
                        batch.append(cls.log_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                        
                if batch:
                    await cls.db.logs.insert_many(batch)
                    
                for _ in batch:
                    cls.log_queue.task_done()
                    
                await asyncio.sleep(2) # Max write frequency
            except asyncio.CancelledError:
                batch = []
                while not cls.log_queue.empty():
                    batch.append(cls.log_queue.get_nowait())
                if batch:
                    await cls.db.logs.insert_many(batch)
                break
            except Exception as e:
                logger.error(f"Log worker error: {e}")
                await asyncio.sleep(2)

    @classmethod
    def log_action_queued(cls, user_id: int, action_type: str, data: dict):
        """Pushes compact logs into memory queue."""
        if cls.log_queue:
            cls.log_queue.put_nowait({
                "ts": datetime.datetime.now(datetime.timezone.utc),
                "uid": user_id,
                "act": action_type,
                "d": data
            })

    # ... KEEP ALL OTHER METHODS AS THEY ARE EXCEPT FOR create_profile ...

    @classmethod
    async def create_profile(cls, user_id: int, username: str = None) -> dict | None:
        if await cls.db.profiles.count_documents({"user_id": user_id}) >= 100:
            return None 

        public_uuid = uuid.uuid4().hex[:8]
        profile = {
            "user_id": user_id,
            "username": username,
            "public_uuid": public_uuid,
            "tags": [],
            "filters": {"require_tags": [], "exclude_tags": [], "any_tags": []},
            "contacts": [], 
            "text": None,
            "media": [], 
            "is_active": False,
            "random_index": random.random(), # Required for fast DB querying
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
        if await cls.db.profiles.count_documents({"user_id": user_id}) == 0:
            profile["is_active"] = True

        res = await cls.db.profiles.insert_one(profile)
        profile["_id"] = res.inserted_id
        
        if username:
            await cls.sync_telegram_username(profile, username)
            
        return await cls.db.profiles.find_one({"_id": profile["_id"]})