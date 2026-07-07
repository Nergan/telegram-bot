import re
import time
import asyncio
import datetime
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict, Any, Optional, Tuple
from domain.interfaces import IUserRepository, IProfileRepository, IContactRequestRepository, ITagRepository, IAlbumRepository
from domain.models import Profile, ContactRequestModel, Tag, ProfileFilters, MediaItem

logger = logging.getLogger(__name__)

class MongoDatabase:
    def __init__(self, uri: str):
        self.client = AsyncIOMotorClient(uri, tls=True, tlsAllowInvalidCertificates=True)
        self.db = self.client["day_dating_bot"]
        self.log_queue = asyncio.Queue()
        self._ban_cache = {}
        self._ban_cache_time = {}

    async def setup_indexes(self):
        await self.db.profiles.create_index([("random_index", 1)])
        await self.db.profiles.create_index([("public_uuid", 1)], unique=True)
        await self.db.users.create_index([("user_id", 1)], unique=True)
        await self.db.user_settings.create_index([("user_id", 1)], unique=True)
        await self.db.search_sessions.create_index([("user_id", 1)], unique=True)
        await self.db.contact_requests.create_index([("req_id", 1)], unique=True)
        await self.db.contact_requests.create_index([("initiator_id", 1)])
        await self.db.contact_requests.create_index([("target_id", 1)])
        await self.db.contact_requests.create_index([("initiator_id", 1), ("target_id", 1), ("status", 1)])
        await self.db.processed_albums.create_index("created_at", expireAfterSeconds=86400)

    def close(self):
        self.client.close()

    async def log_worker(self):
        while True:
            batch = []
            try:
                item = await self.log_queue.get()
                batch.append(item)
                
                while len(batch) < 50:
                    if self.log_queue.empty(): break
                    batch.append(self.log_queue.get_nowait())
                        
                if batch: 
                    await self.db.logs.insert_many(batch)
                for _ in batch: 
                    self.log_queue.task_done()
                batch = []
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                flush_batch = list(batch)
                while not self.log_queue.empty(): 
                    flush_batch.append(self.log_queue.get_nowait())
                if flush_batch:
                    try:
                        await self.db.logs.insert_many(flush_batch)
                    except Exception as e:
                        logger.error(f"Failed to flush logs on shutdown: {e}")
                break
            except Exception as e:
                logger.error(f"Database logging write failed: {e}. Re-queueing logs.")
                for failed_item in batch:
                    self.log_queue.put_nowait(failed_item)
                await asyncio.sleep(5)


class MongoUserRepository(IUserRepository):
    def __init__(self, mongo_db: MongoDatabase):
        self.db = mongo_db.db
        self.mongo_db = mongo_db

    async def set_lang(self, user_id: int, lang: str) -> None:
        await self.db.user_settings.update_one({"user_id": user_id}, {"$set": {"lang": lang}}, upsert=True)

    async def get_lang(self, user_id: int) -> str:
        settings = await self.db.user_settings.find_one({"user_id": user_id})
        return settings.get("lang", "en") if settings else "en"

    async def is_banned(self, user_id: int) -> bool:
        now = time.time()
        if user_id in self.mongo_db._ban_cache and now - self.mongo_db._ban_cache_time.get(user_id, 0) < 60:
            return self.mongo_db._ban_cache[user_id]
        
        user = await self.db.users.find_one({"user_id": user_id})
        is_banned = user.get("is_banned", False) if user else False
        self.mongo_db._ban_cache[user_id] = is_banned
        self.mongo_db._ban_cache_time[user_id] = now
        return is_banned

    async def set_banned(self, user_id: int, banned: bool) -> None:
        await self.db.users.update_one({"user_id": user_id}, {"$set": {"is_banned": banned}}, upsert=True)
        self.mongo_db._ban_cache[user_id] = banned
        self.mongo_db._ban_cache_time[user_id] = time.time()

    def log_action_queued(self, user_id: int, action_type: str, data: dict) -> None:
        self.mongo_db.log_queue.put_nowait({
            "ts": datetime.datetime.now(datetime.timezone.utc),
            "uid": user_id,
            "act": action_type,
            "d": data
        })

    async def add_seen_profile(self, user_id: int, seen_uuid: str) -> None:
        await self.db.search_sessions.update_one({"user_id": user_id}, {"$addToSet": {"seen_uuids": seen_uuid}}, upsert=True)

    async def clear_seen_profiles(self, user_id: int) -> None:
        await self.db.search_sessions.update_one({"user_id": user_id}, {"$set": {"seen_uuids": []}}, upsert=True)

    async def get_seen_profiles(self, user_id: int) -> List[str]:
        session = await self.db.search_sessions.find_one({"user_id": user_id})
        return session.get("seen_uuids", []) if session else []


class MongoProfileRepository(IProfileRepository):
    def __init__(self, mongo_db: MongoDatabase):
        self.db = mongo_db.db

    async def get_by_uuid(self, public_uuid: str) -> Optional[Profile]:
        doc = await self.db.profiles.find_one({"public_uuid": public_uuid})
        return Profile.from_dict(doc) if doc else None

    async def get_active_by_user(self, user_id: int) -> Optional[Profile]:
        doc = await self.db.profiles.find_one({"user_id": user_id, "is_active": True})
        return Profile.from_dict(doc) if doc else None

    async def count_by_user(self, user_id: int) -> int:
        return await self.db.profiles.count_documents({"user_id": user_id})

    async def create(self, profile: Profile) -> Profile:
        res = await self.db.profiles.insert_one(profile.to_dict())
        profile._id = res.inserted_id
        return profile

    async def update(self, profile: Profile) -> None:
        await self.db.profiles.replace_one({"_id": profile._id}, profile.to_dict())

    async def deactivate_all_for_user(self, user_id: int) -> None:
        await self.db.profiles.update_many({"user_id": user_id}, {"$set": {"is_active": False}})

    async def delete(self, user_id: int, public_uuid: str) -> None:
        await self.db.profiles.delete_one({"user_id": user_id, "public_uuid": public_uuid})

    async def delete_inactive_for_user(self, user_id: int) -> None:
        await self.db.profiles.delete_many({"user_id": user_id, "is_active": False})

    async def delete_all_except(self, user_id: int, keep_uuid: str) -> None:
        await self.db.profiles.delete_many({"user_id": user_id, "public_uuid": {"$ne": keep_uuid}})

    async def get_last_by_user(self, user_id: int) -> Optional[Profile]:
        doc = await self.db.profiles.find_one({"user_id": user_id}, sort=[("created_at", -1)])
        return Profile.from_dict(doc) if doc else None

    async def get_pool_size(self, user_id: int, filters: ProfileFilters) -> int:
        and_clauses = [{"user_id": {"$ne": user_id}}, {"is_active": True}]
        if filters.require_tags: and_clauses.append({"tags": {"$all": filters.require_tags}})
        if filters.exclude_tags: and_clauses.append({"tags": {"$nin": filters.exclude_tags}})
        if filters.any_tags: and_clauses.append({"tags": {"$in": filters.any_tags}})
        return await self.db.profiles.count_documents({"$and": and_clauses})

    async def find_next_match(self, user_id: int, seen_uuids: List[str], filters: ProfileFilters, random_index: float, direction: int) -> Optional[Profile]:
        and_clauses = [{"user_id": {"$ne": user_id}}, {"is_active": True}]
        if filters.require_tags: and_clauses.append({"tags": {"$all": filters.require_tags}})
        if filters.exclude_tags: and_clauses.append({"tags": {"$nin": filters.exclude_tags}})
        if filters.any_tags: and_clauses.append({"tags": {"$in": filters.any_tags}})

        op = "$gte" if direction == 1 else "$lt"
        sort_order = 1 if direction == 1 else -1

        match = {"$and": and_clauses + [{"public_uuid": {"$nin": seen_uuids}}, {"random_index": {op: random_index}}]}
        cursor = self.db.profiles.find(match).sort([("random_index", sort_order)]).limit(1)
        profiles = await cursor.to_list(length=1)
        return Profile.from_dict(profiles[0]) if profiles else None

    async def get_all_by_user(self, user_id: int) -> List[Profile]:
        docs = await self.db.profiles.find({"user_id": user_id}).to_list(length=100)
        return [Profile.from_dict(d) for d in docs]
        
    async def get_all_missing_random_index(self) -> List[Profile]:
        docs = await self.db.profiles.find({"random_index": {"$exists": False}}).to_list(None)
        return [Profile.from_dict(d) for d in docs]


class MongoContactRequestRepository(IContactRequestRepository):
    def __init__(self, mongo_db: MongoDatabase):
        self.db = mongo_db.db

    async def create(self, request_model: ContactRequestModel) -> None:
        await self.db.contact_requests.insert_one(request_model.to_dict())

    async def get_by_req_id(self, req_id: str) -> Optional[ContactRequestModel]:
        doc = await self.db.contact_requests.find_one({"req_id": req_id})
        return ContactRequestModel.from_dict(doc) if doc else None

    async def get_pending_by_initiator_target_action(self, initiator_id: int, target_id: int, action: str) -> Optional[ContactRequestModel]:
        doc = await self.db.contact_requests.find_one({"initiator_id": initiator_id, "target_id": target_id, "status": "pending", "action": action})
        return ContactRequestModel.from_dict(doc) if doc else None

    async def update(self, request_model: ContactRequestModel) -> None:
        await self.db.contact_requests.replace_one({"req_id": request_model.req_id}, request_model.to_dict())

    async def count_pending_by_initiator(self, initiator_id: int) -> int:
        return await self.db.contact_requests.count_documents({"initiator_id": initiator_id, "status": "pending"})

    async def count_pending_by_target(self, target_id: int) -> int:
        return await self.db.contact_requests.count_documents({"target_id": target_id, "status": "pending"})

    async def get_pending_actions(self, initiator_id: int, target_id: int) -> List[str]:
        cursor = self.db.contact_requests.find({"initiator_id": initiator_id, "target_id": target_id, "status": "pending"})
        docs = await cursor.to_list(length=10)
        return [doc.get("action") for doc in docs if doc.get("action")]

    async def get_pending_by_initiator(self, initiator_id: int) -> List[ContactRequestModel]:
        docs = await self.db.contact_requests.find({"initiator_id": initiator_id, "status": "pending"}).to_list(length=100)
        return [ContactRequestModel.from_dict(d) for d in docs]

    async def get_pending_by_target(self, target_id: int) -> List[ContactRequestModel]:
        docs = await self.db.contact_requests.find({"target_id": target_id, "status": "pending"}).to_list(length=100)
        return [ContactRequestModel.from_dict(d) for d in docs]


class MongoTagRepository(ITagRepository):
    def __init__(self, mongo_db: MongoDatabase):
        self.db = mongo_db.db

    async def get_by_ids(self, tag_ids: List[str]) -> List[Tag]:
        if not tag_ids: return []
        docs = await self.db.tags.find({"_id": {"$in": tag_ids}}).to_list(length=len(tag_ids))
        return [Tag.from_dict(d) for d in docs]

    async def search(self, query: str, limit: int = 50) -> List[Tag]:
        if not query:
            docs = await self.db.tags.find({"category": {"$nin": ["geo", "age", "language"]}}).to_list(length=limit)
            return [Tag.from_dict(d) for d in docs]
        
        q_lower = query.lower().strip()
        escaped_q = re.escape(q_lower)
        cursor = self.db.tags.find({"search_terms": {"$regex": f"^{escaped_q}"}})
        cursor = cursor.sort([("weight", -1), ("display.en", -1)]).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Tag.from_dict(d) for d in docs]


class MongoAlbumRepository(IAlbumRepository):
    def __init__(self, mongo_db: MongoDatabase):
        self.db = mongo_db.db

    async def is_processed(self, media_group_id: str) -> bool:
        doc = await self.db.processed_albums.find_one({"media_group_id": media_group_id})
        return bool(doc)

    async def mark_processed(self, media_group_id: str) -> None:
        await self.db.processed_albums.insert_one({
            "media_group_id": media_group_id,
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        })

    async def add_to_buffer(self, media_group_id: str, media_item: MediaItem) -> List[MediaItem]:
        res = await self.db.album_buffers.find_one_and_update(
            {"media_group_id": media_group_id},
            {"$push": {"media": media_item.to_dict()}},
            upsert=True,
            return_document=True
        )
        return [MediaItem.from_dict(m) for m in res.get("media", [])]

    async def get_and_clear_buffer(self, media_group_id: str) -> List[MediaItem]:
        doc = await self.db.album_buffers.find_one_and_delete({"media_group_id": media_group_id})
        return [MediaItem.from_dict(m) for m in doc.get("media", [])] if doc else []

    async def clear_buffer(self, media_group_id: str) -> None:
        await self.db.album_buffers.delete_one({"media_group_id": media_group_id})