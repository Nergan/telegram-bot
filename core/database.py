from motor.motor_asyncio import AsyncIOMotorClient
import uuid
import datetime
import time
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
    
    _ban_cache = {}
    _ban_cache_time = {}

    @classmethod
    async def connect(cls):
        cls.client = AsyncIOMotorClient(MONGODB_URI, tls=True, tlsAllowInvalidCertificates=True)
        cls.db = cls.client["day_dating_bot"]
        cls.log_queue = asyncio.Queue()
        await cls.db.profiles.create_index([("random_index", 1)])
        await cls.db.users.create_index([("user_id", 1)], unique=True)
        logger.info("Connected to MongoDB and verified indexes.")

    @classmethod
    def disconnect(cls):
        if cls.client: 
            cls.client.close()
            logger.info("Disconnected from MongoDB.")

    @classmethod
    async def migrate_random_indexes(cls):
        docs = await cls.db.profiles.find({"random_index": {"$exists": False}}).to_list(None)
        for d in docs:
            await cls.db.profiles.update_one({"_id": d["_id"]}, {"$set": {"random_index": random.random()}})

    @classmethod
    async def log_worker(cls):
        while True:
            try:
                batch = []
                item = await cls.log_queue.get()
                batch.append(item)
                
                while len(batch) < 50:
                    if cls.log_queue.empty():
                        break
                    batch.append(cls.log_queue.get_nowait())
                        
                if batch:
                    try:
                        await cls.db.logs.insert_many(batch)
                    except Exception:
                        pass
                    
                for _ in batch:
                    cls.log_queue.task_done()
                    
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                batch = []
                while not cls.log_queue.empty():
                    batch.append(cls.log_queue.get_nowait())
                if batch:
                    try:
                        await cls.db.logs.insert_many(batch)
                    except Exception:
                        pass
                break
            except Exception as e:
                logger.error(f"Log worker error: {e}")
                await asyncio.sleep(2)

    @classmethod
    def log_action_queued(cls, user_id: int, action_type: str, data: dict):
        if cls.log_queue:
            cls.log_queue.put_nowait({
                "ts": datetime.datetime.now(datetime.timezone.utc),
                "uid": user_id,
                "act": action_type,
                "d": data
            })

    @classmethod
    async def set_user_lang(cls, user_id: int, lang: str):
        await cls.db.user_settings.update_one({"user_id": user_id}, {"$set": {"lang": lang}}, upsert=True)

    @classmethod
    async def get_user_lang(cls, user_id: int) -> str:
        settings = await cls.db.user_settings.find_one({"user_id": user_id})
        return settings.get("lang", "en") if settings else "en"

    @classmethod
    async def is_user_banned(cls, user_id: int) -> bool:
        now = time.time()
        if user_id in cls._ban_cache and now - cls._ban_cache_time.get(user_id, 0) < 60:
            return cls._ban_cache[user_id]
        
        user = await cls.db.users.find_one({"user_id": user_id})
        is_banned = user.get("is_banned", False) if user else False
        
        cls._ban_cache[user_id] = is_banned
        cls._ban_cache_time[user_id] = now
        return is_banned

    @classmethod
    async def set_user_banned(cls, user_id: int, banned: bool):
        await cls.db.users.update_one({"user_id": user_id}, {"$set": {"is_banned": banned}}, upsert=True)
        cls._ban_cache[user_id] = banned
        cls._ban_cache_time[user_id] = time.time()

    @classmethod
    async def get_or_create_active_profile(cls, user_id: int, username: str = None) -> dict | None:
        active = await cls.db.profiles.find_one({"user_id": user_id, "is_active": True})
        if active: 
            if username:
                await cls.sync_telegram_username(active, username)
                return await cls.db.profiles.find_one({"_id": active["_id"]})
            return active
        
        if await cls.db.profiles.count_documents({"user_id": user_id}) == 0:
            return await cls.create_profile(user_id, username)
            
        return None
    
    @classmethod
    async def deactivate_profile(cls, user_id: int, profile_uuid: str):
        await cls.db.profiles.update_one({"user_id": user_id, "public_uuid": profile_uuid}, {"$set": {"is_active": False}})
        logger.info(f"User {user_id} deactivated profile {profile_uuid}.")

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
            "random_index": random.random(),
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
        if await cls.db.profiles.count_documents({"user_id": user_id}) == 0:
            profile["is_active"] = True

        res = await cls.db.profiles.insert_one(profile)
        profile["_id"] = res.inserted_id
        
        if username:
            await cls.sync_telegram_username(profile, username)
            
        logger.info(f"Created new profile {public_uuid} for user {user_id}")
        return await cls.db.profiles.find_one({"_id": profile["_id"]})

    @classmethod
    async def sync_telegram_username(cls, profile: dict, username: str):
        if not username:
            return
        contacts = profile.get("contacts", [])
        if not isinstance(contacts, list):
            contacts = []
            
        tg_contact = next((c for c in contacts if c.get("id") == "tg_username"), None)
        val = f"@{username}"
        if not tg_contact:
            contacts.append({
                "id": "tg_username",
                "type": "username",
                "value": val,
                "is_public": False 
            })
            await cls.db.profiles.update_one({"_id": profile["_id"]}, {"$set": {"contacts": contacts}})
        else:
            if tg_contact.get("value") != val:
                tg_contact["value"] = val
                await cls.db.profiles.update_one({"_id": profile["_id"]}, {"$set": {"contacts": contacts}})

    @classmethod
    async def set_active_profile(cls, user_id: int, profile_uuid: str):
        await cls.db.profiles.update_many({"user_id": user_id}, {"$set": {"is_active": False}})
        await cls.db.profiles.update_one({"user_id": user_id, "public_uuid": profile_uuid}, {"$set": {"is_active": True}})
        logger.info(f"User {user_id} set profile {profile_uuid} as active.")

    @classmethod
    async def get_active_profile(cls, user_id: int):
        return await cls.db.profiles.find_one({"user_id": user_id, "is_active": True})

    @classmethod
    async def get_profile_by_uuid(cls, public_uuid: str):
        return await cls.db.profiles.find_one({"public_uuid": public_uuid})
        
    @classmethod
    async def delete_profile(cls, user_id: int, public_uuid: str) -> bool:
        if await cls.db.profiles.count_documents({"user_id": user_id}) <= 1:
            return False 
        await cls.db.profiles.delete_one({"user_id": user_id, "public_uuid": public_uuid})
        return True

    @classmethod
    async def delete_all_but_active(cls, user_id: int):
        active = await cls.get_active_profile(user_id)
        if active:
            await cls.db.profiles.delete_many({"user_id": user_id, "is_active": False})
        else:
            last_profile = await cls.db.profiles.find_one({"user_id": user_id}, sort=[("created_at", -1)])
            if last_profile:
                await cls.db.profiles.delete_many({"user_id": user_id, "_id": {"$ne": last_profile["_id"]}})
        
    @classmethod
    async def get_pool_size(cls, user_id: int, filters: dict = None) -> int:
        and_clauses = [{"user_id": {"$ne": user_id}}, {"is_active": True}]
        if filters:
            if filters.get("require_tags"): 
                and_clauses.append({"tags": {"$all": filters["require_tags"]}})
            if filters.get("exclude_tags"): 
                and_clauses.append({"tags": {"$nin": filters["exclude_tags"]}})
            if filters.get("any_tags"): 
                and_clauses.append({"tags": {"$in": filters["any_tags"]}})
        
        return await cls.db.profiles.count_documents({"$and": and_clauses})
        
    @classmethod
    async def add_seen_profile(cls, user_id: int, seen_uuid: str):
        await cls.db.search_sessions.update_one(
            {"user_id": user_id}, 
            {"$addToSet": {"seen_uuids": seen_uuid}}, 
            upsert=True
        )

    @classmethod
    async def clear_seen_profiles(cls, user_id: int):
        await cls.db.search_sessions.update_one(
            {"user_id": user_id}, 
            {"$set": {"seen_uuids": []}}, 
            upsert=True
        )

    @classmethod
    async def get_seen_profiles(cls, user_id: int) -> list:
        session = await cls.db.search_sessions.find_one({"user_id": user_id})
        return session.get("seen_uuids", []) if session else []

    @classmethod
    async def get_requests_counts(cls, user_id: int) -> tuple[int, int]:
        sent = await cls.db.contact_requests.count_documents({
            "initiator_id": user_id, 
            "status": "pending"
        })
        recv = await cls.db.contact_requests.count_documents({
            "target_id": user_id, 
            "status": "pending"
        })
        return sent, recv
    
    @classmethod
    async def get_tags_by_ids(cls, tag_ids: list) -> list:
        if not tag_ids: return []
        cursor = cls.db.tags.find({"_id": {"$in": tag_ids}})
        return await cursor.to_list(length=len(tag_ids))

    @classmethod
    async def search_tags(cls, query: str, limit: int = 50) -> list:
        if not query:
            cursor = cls.db.tags.find(
                {"category": {"$nin": ["geo", "age", "language"]}}
            )
            return await cursor.to_list(length=None)
        
        q_lower = query.lower().strip()
        cursor = cls.db.tags.find({"search_terms": {"$regex": f"^{q_lower}"}})
        cursor = cursor.sort([("weight", -1), ("display.en", -1)]).limit(limit)
        return await cursor.to_list(length=limit)