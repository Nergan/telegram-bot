from motor.motor_asyncio import AsyncIOMotorClient
import uuid
import datetime
from core.config import MONGODB_URI
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    def connect(cls):
        cls.client = AsyncIOMotorClient(MONGODB_URI, tls=True, tlsAllowInvalidCertificates=True)
        cls.db = cls.client["day_dating_bot"]
        logger.info("Connected to MongoDB.")

    @classmethod
    def disconnect(cls):
        if cls.client: 
            cls.client.close()
            logger.info("Disconnected from MongoDB.")

    @classmethod
    async def log_action(cls, user_id: int, action_type: str, data: dict):
        await cls.db.logs.insert_one({
            "timestamp": datetime.datetime.now(datetime.timezone.utc),
            "user_id": user_id,
            "action_type": action_type,
            "data": data
        })

    @classmethod
    async def get_or_create_active_profile(cls, user_id: int, username: str = None) -> dict:
        active = await cls.db.profiles.find_one({"user_id": user_id, "is_active": True})
        if active: 
            if username:
                await cls.sync_telegram_username(active, username)
            return await cls.db.profiles.find_one({"_id": active["_id"]})
        
        any_profile = await cls.db.profiles.find_one({"user_id": user_id})
        if any_profile:
            await cls.set_active_profile(user_id, any_profile['public_uuid'])
            active_fresh = await cls.db.profiles.find_one({"public_uuid": any_profile['public_uuid']})
            if username:
                await cls.sync_telegram_username(active_fresh, username)
            return await cls.db.profiles.find_one({"public_uuid": any_profile['public_uuid']})
            
        return await cls.create_profile(user_id, username)

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
        active = await cls.db.profiles.find_one({"user_id": user_id, "is_active": True})
        if not active:
            any_prof = await cls.db.profiles.find_one({"user_id": user_id})
            if any_prof: await cls.set_active_profile(user_id, any_prof['public_uuid'])
        return True

    @classmethod
    async def delete_all_but_active(cls, user_id: int):
        await cls.db.profiles.delete_many({"user_id": user_id, "is_active": False})
        
    @classmethod
    async def get_pool_size(cls, user_id: int) -> int:
        return await cls.db.profiles.count_documents({"user_id": {"$ne": user_id}, "is_active": True})
        
    # --- Session Tracking ---
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
        logger.info(f"Pending requests count for {user_id}: sent={sent}, recv={recv}")
        return sent, recv