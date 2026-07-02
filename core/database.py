from motor.motor_asyncio import AsyncIOMotorClient
import uuid
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
        if cls.client:
            cls.client.close()

    @classmethod
    async def get_or_create_profile(cls, user_id: int) -> dict:
        profile = await cls.db.profiles.find_one({"user_id": user_id})
        if not profile:
            public_uuid = uuid.uuid4().hex[:8]
            profile = {
                "user_id": user_id,
                "public_uuid": public_uuid,
                "tags": [],
                "text": None,
                "media": None,
                "score": 0
            }
            await cls.db.profiles.insert_one(profile)
        return profile