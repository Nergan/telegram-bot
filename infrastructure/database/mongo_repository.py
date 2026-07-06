import time
import asyncio
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict, Any, Optional, Tuple
from domain.interfaces import IUserRepository, IProfileRepository, IContactRequestRepository, ITagRepository

class MongoDatabase:
    def __init__(self, uri: str):
        self.client = AsyncIOMotorClient(uri, tls=True, tlsAllowInvalidCertificates=True)
        self.db = self.client["day_dating_bot"]
        self.log_queue = asyncio.Queue()
        self._ban_cache = {}
        self._ban_cache_time = {}

    async def setup_indexes(self):
        await self.db.profiles.create_index([("random_index", 1)])
        await self.db.users.create_index([("user_id", 1)], unique=True)

    def close(self):
        self.client.close()

    async def log_worker(self):
        while True:
            try:
                batch = []
                item = await self.log_queue.get()
                batch.append(item)
                
                while len(batch) < 50:
                    if self.log_queue.empty(): break
                    batch.append(self.log_queue.get_nowait())
                        
                if batch: await self.db.logs.insert_many(batch)
                for _ in batch: self.log_queue.task_done()
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                batch = []
                while not self.log_queue.empty(): batch.append(self.log_queue.get_nowait())
                if batch: await self.db.logs.insert_many(batch)
                break
            except Exception:
                await asyncio.sleep(2)


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

    async def get_by_uuid(self, public_uuid: str) -> Optional[Dict[str, Any]]:
        return await self.db.profiles.find_one({"public_uuid": public_uuid})

    async def get_active_by_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await self.db.profiles.find_one({"user_id": user_id, "is_active": True})

    async def count_by_user(self, user_id: int) -> int:
        return await self.db.profiles.count_documents({"user_id": user_id})

    async def create(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        res = await self.db.profiles.insert_one(profile)
        profile["_id"] = res.inserted_id
        return profile

    async def update(self, public_uuid: str, update_data: Dict[str, Any]) -> None:
        await self.db.profiles.update_one({"public_uuid": public_uuid}, {"$set": update_data})

    async def update_by_id(self, _id: Any, update_data: Dict[str, Any]) -> None:
        await self.db.profiles.update_one({"_id": _id}, {"$set": update_data})

    async def update_many_by_user(self, user_id: int, update_data: Dict[str, Any]) -> None:
        await self.db.profiles.update_many({"user_id": user_id}, {"$set": update_data})

    async def delete(self, user_id: int, public_uuid: str) -> None:
        await self.db.profiles.delete_one({"user_id": user_id, "public_uuid": public_uuid})

    async def delete_many(self, query: Dict[str, Any]) -> None:
        await self.db.profiles.delete_many(query)

    async def get_last_by_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await self.db.profiles.find_one({"user_id": user_id}, sort=[("created_at", -1)])

    async def get_pool_size(self, user_id: int, filters: Optional[Dict[str, Any]] = None) -> int:
        and_clauses = [{"user_id": {"$ne": user_id}}, {"is_active": True}]
        if filters:
            if filters.get("require_tags"): and_clauses.append({"tags": {"$all": filters["require_tags"]}})
            if filters.get("exclude_tags"): and_clauses.append({"tags": {"$nin": filters["exclude_tags"]}})
            if filters.get("any_tags"): and_clauses.append({"tags": {"$in": filters["any_tags"]}})
        return await self.db.profiles.count_documents({"$and": and_clauses})

    async def find_one_matching(self, query: Dict[str, Any], sort_args: List[Tuple[str, int]]) -> Optional[Dict[str, Any]]:
        cursor = self.db.profiles.find(query).sort(sort_args).limit(1)
        profiles = await cursor.to_list(length=1)
        return profiles[0] if profiles else None

    async def get_all_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        return await self.db.profiles.find({"user_id": user_id}).to_list(length=100)
        
    async def get_all_missing_random_index(self) -> List[Dict[str, Any]]:
        return await self.db.profiles.find({"random_index": {"$exists": False}}).to_list(None)


class MongoContactRequestRepository(IContactRequestRepository):
    def __init__(self, mongo_db: MongoDatabase):
        self.db = mongo_db.db

    async def create(self, request_doc: Dict[str, Any]) -> None:
        await self.db.contact_requests.insert_one(request_doc)

    async def get_by_req_id(self, req_id: str) -> Optional[Dict[str, Any]]:
        return await self.db.contact_requests.find_one({"req_id": req_id})

    async def get_pending_by_initiator_target_action(self, initiator_id: int, target_id: int, action: str) -> Optional[Dict[str, Any]]:
        return await self.db.contact_requests.find_one({"initiator_id": initiator_id, "target_id": target_id, "status": "pending", "action": action})

    async def update_status(self, req_id: str, status: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        update = {"status": status}
        if extra_data: update.update(extra_data)
        await self.db.contact_requests.update_one({"req_id": req_id}, {"$set": update})

    async def count_pending_by_initiator(self, initiator_id: int) -> int:
        return await self.db.contact_requests.count_documents({"initiator_id": initiator_id, "status": "pending"})

    async def count_pending_by_target(self, target_id: int) -> int:
        return await self.db.contact_requests.count_documents({"target_id": target_id, "status": "pending"})

    async def get_pending_actions(self, initiator_id: int, target_id: int) -> List[str]:
        cursor = self.db.contact_requests.find({"initiator_id": initiator_id, "target_id": target_id, "status": "pending"})
        docs = await cursor.to_list(length=10)
        return [doc.get("action") for doc in docs if doc.get("action")]

    async def get_pending_by_initiator(self, initiator_id: int) -> List[Dict[str, Any]]:
        return await self.db.contact_requests.find({"initiator_id": initiator_id, "status": "pending"}).to_list(length=100)

    async def get_pending_by_target(self, target_id: int) -> List[Dict[str, Any]]:
        return await self.db.contact_requests.find({"target_id": target_id, "status": "pending"}).to_list(length=100)


class MongoTagRepository(ITagRepository):
    def __init__(self, mongo_db: MongoDatabase):
        self.db = mongo_db.db

    async def get_by_ids(self, tag_ids: List[str]) -> List[Dict[str, Any]]:
        if not tag_ids: return []
        return await self.db.tags.find({"_id": {"$in": tag_ids}}).to_list(length=len(tag_ids))

    async def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not query:
            return await self.db.tags.find({"category": {"$nin": ["geo", "age", "language"]}}).to_list(length=None)
        
        q_lower = query.lower().strip()
        cursor = self.db.tags.find({"search_terms": {"$regex": f"^{q_lower}"}})
        cursor = cursor.sort([("weight", -1), ("display.en", -1)]).limit(limit)
        return await cursor.to_list(length=limit)