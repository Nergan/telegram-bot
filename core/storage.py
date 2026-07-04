from typing import Dict, Any, Optional
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from core.database import Database

class MongoStorage(BaseStorage):
    """Custom MongoDB FSM Storage to persist FSM sessions across Render restarts."""
    
    async def set_state(self, key: StorageKey, state: str = None) -> None:
        coll = Database.db.fsm_data
        if state is None:
            await coll.update_one(
                {"chat_id": key.chat_id, "user_id": key.user_id}, 
                {"$unset": {"state": ""}}, 
                upsert=True
            )
        else:
            s = state.state if hasattr(state, 'state') else state
            await coll.update_one(
                {"chat_id": key.chat_id, "user_id": key.user_id}, 
                {"$set": {"state": s}}, 
                upsert=True
            )

    async def get_state(self, key: StorageKey) -> Optional[str]:
        coll = Database.db.fsm_data
        doc = await coll.find_one({"chat_id": key.chat_id, "user_id": key.user_id})
        return doc.get("state") if doc else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        coll = Database.db.fsm_data
        await coll.update_one(
            {"chat_id": key.chat_id, "user_id": key.user_id}, 
            {"$set": {"data": data}}, 
            upsert=True
        )

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        coll = Database.db.fsm_data
        doc = await coll.find_one({"chat_id": key.chat_id, "user_id": key.user_id})
        return doc.get("data", {}) if doc else {}

    async def close(self) -> None:
        pass