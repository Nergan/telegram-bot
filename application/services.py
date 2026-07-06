import uuid
import random
import datetime
import logging
from typing import Optional, Dict, Any, List, Tuple
from domain.interfaces import IUserRepository, IProfileRepository, IContactRequestRepository, ITagRepository

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, user_repo: IUserRepository):
        self.user_repo = user_repo

    async def set_lang(self, user_id: int, lang: str) -> None:
        await self.user_repo.set_lang(user_id, lang)

    async def get_lang(self, user_id: int) -> str:
        return await self.user_repo.get_lang(user_id)

    async def is_banned(self, user_id: int) -> bool:
        return await self.user_repo.is_banned(user_id)
        
    def log_action(self, user_id: int, action_type: str, data: dict) -> None:
        self.user_repo.log_action_queued(user_id, action_type, data)


class ProfileService:
    def __init__(self, profile_repo: IProfileRepository):
        self.profile_repo = profile_repo

    async def get_or_create_active_profile(self, user_id: int, username: Optional[str] = None) -> Optional[Dict[str, Any]]:
        active = await self.profile_repo.get_active_by_user(user_id)
        if active:
            if username:
                await self.sync_telegram_username(active, username)
                return await self.profile_repo.get_by_uuid(active["public_uuid"])
            return active
        
        count = await self.profile_repo.count_by_user(user_id)
        if count == 0:
            return await self.create_profile(user_id, username)
        return None

    async def create_profile(self, user_id: int, username: Optional[str] = None) -> Optional[Dict[str, Any]]:
        count = await self.profile_repo.count_by_user(user_id)
        if count >= 100:
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
            "is_active": count == 0,
            "random_index": random.random(),
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }

        created = await self.profile_repo.create(profile)
        if username:
            await self.sync_telegram_username(created, username)
        logger.info(f"Created new profile {public_uuid} for user {user_id}")
        return await self.profile_repo.get_by_uuid(public_uuid)

    async def sync_telegram_username(self, profile: Dict[str, Any], username: str) -> None:
        if not username: return
        contacts = profile.get("contacts", [])
        if not isinstance(contacts, list): contacts = []
            
        tg_contact = next((c for c in contacts if c.get("id") == "tg_username"), None)
        val = f"@{username}"
        if not tg_contact:
            contacts.append({"id": "tg_username", "type": "username", "value": val, "is_public": False})
            await self.profile_repo.update_by_id(profile["_id"], {"contacts": contacts})
        else:
            if tg_contact.get("value") != val:
                tg_contact["value"] = val
                await self.profile_repo.update_by_id(profile["_id"], {"contacts": contacts})

    async def set_active_profile(self, user_id: int, profile_uuid: str) -> None:
        await self.profile_repo.update_many_by_user(user_id, {"is_active": False})
        await self.profile_repo.update(profile_uuid, {"is_active": True})

    async def deactivate_profile(self, user_id: int, profile_uuid: str) -> None:
        await self.profile_repo.update(profile_uuid, {"is_active": False})

    async def delete_profile(self, user_id: int, public_uuid: str) -> bool:
        if await self.profile_repo.count_by_user(user_id) <= 1: return False 
        await self.profile_repo.delete(user_id, public_uuid)
        return True

    async def delete_all_but_active(self, user_id: int) -> None:
        if await self.profile_repo.get_active_by_user(user_id):
            await self.profile_repo.delete_many({"user_id": user_id, "is_active": False})
        else:
            last_profile = await self.profile_repo.get_last_by_user(user_id)
            if last_profile:
                await self.profile_repo.delete_many({"user_id": user_id, "_id": {"$ne": last_profile["_id"]}})

    async def get_pool_size(self, user_id: int, filters: Optional[Dict[str, Any]] = None) -> int:
        return await self.profile_repo.get_pool_size(user_id, filters)

    async def get_active_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await self.profile_repo.get_active_by_user(user_id)

    async def get_profile_by_uuid(self, public_uuid: str) -> Optional[Dict[str, Any]]:
        return await self.profile_repo.get_by_uuid(public_uuid)

    async def get_all_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        return await self.profile_repo.get_all_by_user(user_id)

    async def update_profile(self, public_uuid: str, update_data: dict) -> None:
        await self.profile_repo.update(public_uuid, update_data)


class BrowseService:
    def __init__(self, profile_repo: IProfileRepository, user_repo: IUserRepository):
        self.profile_repo = profile_repo
        self.user_repo = user_repo

    async def get_next_profile(self, user_id: int, active_profile: dict) -> Tuple[Optional[Dict[str, Any]], bool]:
        seen_uuids = await self.user_repo.get_seen_profiles(user_id)
        filters = active_profile.get("filters") or {}
        
        and_clauses = [{"user_id": {"$ne": user_id}}, {"is_active": True}]
        if filters.get("require_tags"): and_clauses.append({"tags": {"$all": filters["require_tags"]}})
        if filters.get("exclude_tags"): and_clauses.append({"tags": {"$nin": filters["exclude_tags"]}})
        if filters.get("any_tags"): and_clauses.append({"tags": {"$in": filters["any_tags"]}})
            
        r_idx = random.random()
        match_fwd = {"$and": and_clauses + [{"public_uuid": {"$nin": seen_uuids}}, {"random_index": {"$gte": r_idx}}]}
        target = await self.profile_repo.find_one_matching(match_fwd, [("random_index", 1)])
        
        if not target:
            match_bwd = {"$and": and_clauses + [{"public_uuid": {"$nin": seen_uuids}}, {"random_index": {"$lt": r_idx}}]}
            target = await self.profile_repo.find_one_matching(match_bwd, [("random_index", -1)])
            
        all_seen = False
        if not target:
            match_all_fwd = {"$and": and_clauses + [{"random_index": {"$gte": r_idx}}]}
            target = await self.profile_repo.find_one_matching(match_all_fwd, [("random_index", 1)])
            
            if not target:
                match_all_bwd = {"$and": and_clauses + [{"random_index": {"$lt": r_idx}}]}
                target = await self.profile_repo.find_one_matching(match_all_bwd, [("random_index", -1)])
                
            if target:
                await self.user_repo.clear_seen_profiles(user_id)
                all_seen = True

        if target:
            await self.user_repo.add_seen_profile(user_id, target.get('public_uuid', ''))
            
        return target, all_seen


class ContactRequestService:
    def __init__(self, req_repo: IContactRequestRepository):
        self.req_repo = req_repo

    async def get_pending_actions(self, initiator_id: int, target_id: int) -> List[str]:
        outbound = await self.req_repo.get_pending_actions(initiator_id, target_id)
        inbound = await self.req_repo.get_pending_actions(target_id, initiator_id)
        return list(set(outbound + inbound))

    async def get_requests_counts(self, user_id: int) -> Tuple[int, int]:
        return (await self.req_repo.count_pending_by_initiator(user_id), await self.req_repo.count_pending_by_target(user_id))

    async def has_pending_request(self, initiator_id: int, target_id: int, action: str) -> bool:
        req_out = await self.req_repo.get_pending_by_initiator_target_action(initiator_id, target_id, action)
        req_in = await self.req_repo.get_pending_by_initiator_target_action(target_id, initiator_id, action)
        return req_out is not None or req_in is not None

    async def create_request(self, initiator_id: int, target_id: int, action: str, message: str, shared_contacts: list) -> str:
        req_id = uuid.uuid4().hex
        await self.req_repo.create({
            "req_id": req_id, "initiator_id": initiator_id, "target_id": target_id, 
            "action": action, "status": "pending", "message": message, "shared_contacts": shared_contacts
        })
        return req_id

    async def get_request(self, req_id: str) -> Optional[Dict[str, Any]]:
        return await self.req_repo.get_by_req_id(req_id)

    async def update_status(self, req_id: str, status: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        await self.req_repo.update_status(req_id, status, extra_data)

    async def get_pending_by_initiator(self, initiator_id: int) -> List[Dict[str, Any]]:
        return await self.req_repo.get_pending_by_initiator(initiator_id)

    async def get_pending_by_target(self, target_id: int) -> List[Dict[str, Any]]:
        return await self.req_repo.get_pending_by_target(target_id)


class TagService:
    def __init__(self, tag_repo: ITagRepository):
        self.tag_repo = tag_repo

    async def get_tags_by_ids(self, tag_ids: List[str]) -> List[Dict[str, Any]]:
        return await self.tag_repo.get_by_ids(tag_ids)

    async def search_tags(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        return await self.tag_repo.search(query, limit)