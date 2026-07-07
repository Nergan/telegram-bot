import uuid
import random
import datetime
import logging
from typing import Optional, Dict, Any, List, Tuple
from domain.interfaces import IUserRepository, IProfileRepository, IContactRequestRepository, ITagRepository, IAlbumRepository
from domain.models import Profile, Contact, ProfileFilters, MediaItem, ContactRequestModel, Tag

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

    async def get_or_create_active_profile(self, user_id: int, username: Optional[str] = None) -> Optional[Profile]:
        active = await self.profile_repo.get_active_by_user(user_id)
        if active:
            if username:
                await self.sync_telegram_username(active, username)
                return await self.profile_repo.get_by_uuid(active.public_uuid)
            return active
        
        count = await self.profile_repo.count_by_user(user_id)
        if count == 0:
            return await self.create_profile(user_id, username)
        return None

    async def create_profile(self, user_id: int, username: Optional[str] = None) -> Optional[Profile]:
        count = await self.profile_repo.count_by_user(user_id)
        if count >= 100:
            return None 

        public_uuid = uuid.uuid4().hex[:8]
        profile = Profile(
            user_id=user_id,
            public_uuid=public_uuid,
            is_active=(count == 0),
            random_index=random.random(),
            created_at=datetime.datetime.now(datetime.timezone.utc),
            username=username
        )

        created = await self.profile_repo.create(profile)
        if username:
            await self.sync_telegram_username(created, username)
        logger.info(f"Created new profile {public_uuid} for user {user_id}")
        return created

    async def sync_telegram_username(self, profile: Profile, username: str) -> None:
        if not username: return
        tg_contact = next((c for c in profile.contacts if c.id == "tg_username"), None)
        val = f"@{username}"
        if not tg_contact:
            profile.contacts.append(Contact(id="tg_username", type="username", value=val, is_public=False))
            await self.profile_repo.update(profile)
        else:
            if tg_contact.value != val:
                tg_contact.value = val
                await self.profile_repo.update(profile)

    async def set_active_profile(self, user_id: int, profile_uuid: str) -> None:
        await self.profile_repo.deactivate_all_for_user(user_id)
        target = await self.profile_repo.get_by_uuid(profile_uuid)
        if target:
            target.is_active = True
            await self.profile_repo.update(target)

    async def deactivate_profile(self, user_id: int, profile_uuid: str) -> None:
        target = await self.profile_repo.get_by_uuid(profile_uuid)
        if target:
            target.is_active = False
            await self.profile_repo.update(target)

    async def delete_profile(self, user_id: int, public_uuid: str) -> bool:
        if await self.profile_repo.count_by_user(user_id) <= 1: return False 
        await self.profile_repo.delete(user_id, public_uuid)
        return True

    async def delete_all_but_active(self, user_id: int) -> None:
        active = await self.profile_repo.get_active_by_user(user_id)
        if active:
            await self.profile_repo.delete_inactive_for_user(user_id)
        else:
            last_profile = await self.profile_repo.get_last_by_user(user_id)
            if last_profile:
                await self.profile_repo.delete_all_except(user_id, last_profile.public_uuid)

    async def get_pool_size(self, user_id: int, filters: ProfileFilters) -> int:
        return await self.profile_repo.get_pool_size(user_id, filters)

    async def get_active_profile(self, user_id: int) -> Optional[Profile]:
        return await self.profile_repo.get_active_by_user(user_id)

    async def get_profile_by_uuid(self, public_uuid: str) -> Optional[Profile]:
        return await self.profile_repo.get_by_uuid(public_uuid)

    async def get_all_by_user(self, user_id: int) -> List[Profile]:
        return await self.profile_repo.get_all_by_user(user_id)

    async def update_profile(self, profile: Profile) -> None:
        await self.profile_repo.update(profile)


class BrowseService:
    def __init__(self, profile_repo: IProfileRepository, user_repo: IUserRepository):
        self.profile_repo = profile_repo
        self.user_repo = user_repo

    async def get_next_profile(self, user_id: int, active_profile: Profile) -> Tuple[Optional[Profile], bool]:
        seen_uuids = await self.user_repo.get_seen_profiles(user_id)
        filters = active_profile.filters
        r_idx = random.random()
        
        target = await self.profile_repo.find_next_match(user_id, seen_uuids, filters, r_idx, 1)
        if not target:
            target = await self.profile_repo.find_next_match(user_id, seen_uuids, filters, r_idx, -1)
            
        all_seen = False
        if not target:
            target = await self.profile_repo.find_next_match(user_id, [], filters, r_idx, 1)
            if not target:
                target = await self.profile_repo.find_next_match(user_id, [], filters, r_idx, -1)
                
            if target:
                await self.user_repo.clear_seen_profiles(user_id)
                all_seen = True

        if target:
            await self.user_repo.add_seen_profile(user_id, target.public_uuid)
            
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
        req = ContactRequestModel(
            req_id=req_id, initiator_id=initiator_id, target_id=target_id,
            action=action, status="pending", message=message, shared_contacts=shared_contacts
        )
        await self.req_repo.create(req)
        return req_id

    async def get_request(self, req_id: str) -> Optional[ContactRequestModel]:
        return await self.req_repo.get_by_req_id(req_id)

    async def update_status(self, req_id: str, status: str, target_shared_contacts: Optional[List[str]] = None) -> None:
        req = await self.req_repo.get_by_req_id(req_id)
        if req:
            req.status = status
            if target_shared_contacts is not None:
                req.target_shared_contacts = target_shared_contacts
            await self.req_repo.update(req)

    async def get_pending_by_initiator(self, initiator_id: int) -> List[ContactRequestModel]:
        return await self.req_repo.get_pending_by_initiator(initiator_id)

    async def get_pending_by_target(self, target_id: int) -> List[ContactRequestModel]:
        return await self.req_repo.get_pending_by_target(target_id)


class TagService:
    def __init__(self, tag_repo: ITagRepository):
        self.tag_repo = tag_repo

    async def get_tags_by_ids(self, tag_ids: List[str]) -> List[Tag]:
        return await self.tag_repo.get_by_ids(tag_ids)

    async def search_tags(self, query: str, limit: int = 50) -> List[Tag]:
        return await self.tag_repo.search(query, limit)


class AlbumService:
    def __init__(self, album_repo: IAlbumRepository):
        self.album_repo = album_repo

    async def is_processed(self, media_group_id: str) -> bool:
        return await self.album_repo.is_processed(media_group_id)

    async def mark_processed(self, media_group_id: str) -> None:
        await self.album_repo.mark_processed(media_group_id)

    async def add_to_buffer(self, media_group_id: str, media_item: MediaItem) -> List[MediaItem]:
        return await self.album_repo.add_to_buffer(media_group_id, media_item)

    async def get_and_clear_buffer(self, media_group_id: str) -> List[MediaItem]:
        return await self.album_repo.get_and_clear_buffer(media_group_id)

    async def clear_buffer(self, media_group_id: str) -> None:
        await self.album_repo.clear_buffer(media_group_id)