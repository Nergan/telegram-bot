from motor.motor_asyncio import AsyncIOMotorClient
import uuid
import datetime
from core.config import MONGODB_URI

class Database:
    client: AsyncIOMotorClient = None
    db = None

    @classmethod
    def connect(cls):
        cls.client = AsyncIOMotorClient(MONGODB_URI, tls=True, tlsAllowInvalidCertificates=True)
        cls.db = cls.client["day_dating_bot"]

    @classmethod
    def disconnect(cls):
        if cls.client: cls.client.close()

    @classmethod
    async def log_action(cls, user_id: int, action_type: str, data: dict):
        await cls.db.logs.insert_one({
            "timestamp": datetime.datetime.now(datetime.timezone.utc),
            "user_id": user_id,
            "action_type": action_type,
            "data": data
        })

    @classmethod
    async def get_or_create_active_profile(cls, user_id: int) -> dict:
        active = await cls.db.profiles.find_one({"user_id": user_id, "is_active": True})
        if active: return active
        
        any_profile = await cls.db.profiles.find_one({"user_id": user_id})
        if any_profile:
            await cls.set_active_profile(user_id, any_profile['public_uuid'])
            return await cls.db.profiles.find_one({"public_uuid": any_profile['public_uuid']})
            
        return await cls.create_profile(user_id)

    @classmethod
    async def create_profile(cls, user_id: int) -> dict:
        public_uuid = uuid.uuid4().hex[:8]
        profile = {
            "user_id": user_id,
            "public_uuid": public_uuid,
            "tags": [],
            "filters": {"require_tags": [], "exclude_tags": [], "any_tags": []},
            "text": None,
            "media": {"items": [], "voice": None}, # items: up to 5 {type, file_id}
            "public_contact": None,
            "private_contact": None,
            "is_active": False,
            "is_hidden": False,
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
        if await cls.db.profiles.count_documents({"user_id": user_id}) == 0:
            profile["is_active"] = True

        res = await cls.db.profiles.insert_one(profile)
        profile["_id"] = res.inserted_id
        return profile

    @classmethod
    async def set_active_profile(cls, user_id: int, profile_uuid: str):
        await cls.db.profiles.update_many({"user_id": user_id}, {"$set": {"is_active": False}})
        await cls.db.profiles.update_one({"user_id": user_id, "public_uuid": profile_uuid}, {"$set": {"is_active": True}})

    @classmethod
    async def get_active_profile(cls, user_id: int):
        return await cls.db.profiles.find_one({"user_id": user_id, "is_active": True})

    @classmethod
    async def get_profile_by_uuid(cls, public_uuid: str):
        return await cls.db.profiles.find_one({"public_uuid": public_uuid})
        
    @classmethod
    async def delete_profile(cls, user_id: int, public_uuid: str) -> bool:
        if await cls.db.profiles.count_documents({"user_id": user_id}) <= 1:
            return False # Prevent deleting last profile
            
        await cls.db.profiles.delete_one({"user_id": user_id, "public_uuid": public_uuid})
        active = await cls.db.profiles.find_one({"user_id": user_id, "is_active": True})
        if not active:
            any_prof = await cls.db.profiles.find_one({"user_id": user_id})
            if any_prof: await cls.set_active_profile(user_id, any_prof['public_uuid'])
        return True