from typing import Dict, Any, Optional
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from infrastructure.database.mongo_repository import MongoDatabase

class MongoFSMStorage(BaseStorage):
    def __init__(self, mongo_db: MongoDatabase):
        self.db = mongo_db.db
    
    async def set_state(self, key: StorageKey, state: str = None) -> None:
        coll = self.db.fsm_data
        if state is None:
            await coll.update_one({"chat_id": key.chat_id, "user_id": key.user_id}, {"$unset": {"state": ""}}, upsert=True)
        else:
            s = state.state if hasattr(state, 'state') else state
            await coll.update_one({"chat_id": key.chat_id, "user_id": key.user_id}, {"$set": {"state": s}}, upsert=True)

    async def get_state(self, key: StorageKey) -> Optional[str]:
        doc = await self.db.fsm_data.find_one({"chat_id": key.chat_id, "user_id": key.user_id})
        return doc.get("state") if doc else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        await self.db.fsm_data.update_one({"chat_id": key.chat_id, "user_id": key.user_id}, {"$set": {"data": data}}, upsert=True)

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        doc = await self.db.fsm_data.find_one({"chat_id": key.chat_id, "user_id": key.user_id})
        return doc.get("data", {}) if doc else {}

    async def close(self) -> None:
        pass