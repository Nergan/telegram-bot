from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from domain.models import Profile, ProfileFilters, ContactRequestModel, Tag, MediaItem

class IUserRepository(ABC):
    @abstractmethod
    async def set_lang(self, user_id: int, lang: str) -> None: pass
    
    @abstractmethod
    async def get_lang(self, user_id: int) -> str: pass
    
    @abstractmethod
    async def is_banned(self, user_id: int) -> bool: pass
    
    @abstractmethod
    async def set_banned(self, user_id: int, banned: bool) -> None: pass
    
    @abstractmethod
    def log_action_queued(self, user_id: int, action_type: str, data: dict) -> None: pass
    
    @abstractmethod
    async def add_seen_profile(self, user_id: int, seen_uuid: str) -> None: pass
    
    @abstractmethod
    async def clear_seen_profiles(self, user_id: int) -> None: pass
    
    @abstractmethod
    async def get_seen_profiles(self, user_id: int) -> List[str]: pass


class IProfileRepository(ABC):
    @abstractmethod
    async def get_by_uuid(self, public_uuid: str) -> Optional[Profile]: pass
    
    @abstractmethod
    async def get_active_by_user(self, user_id: int) -> Optional[Profile]: pass
    
    @abstractmethod
    async def count_by_user(self, user_id: int) -> int: pass
    
    @abstractmethod
    async def create(self, profile: Profile) -> Profile: pass
    
    @abstractmethod
    async def update(self, profile: Profile) -> None: pass
    
    @abstractmethod
    async def deactivate_all_for_user(self, user_id: int) -> None: pass
    
    @abstractmethod
    async def delete(self, user_id: int, public_uuid: str) -> None: pass
    
    @abstractmethod
    async def delete_inactive_for_user(self, user_id: int) -> None: pass
    
    @abstractmethod
    async def delete_all_except(self, user_id: int, keep_uuid: str) -> None: pass
    
    @abstractmethod
    async def get_last_by_user(self, user_id: int) -> Optional[Profile]: pass
    
    @abstractmethod
    async def get_pool_size(self, user_id: int, filters: ProfileFilters) -> int: pass
    
    @abstractmethod
    async def find_next_match(self, user_id: int, seen_uuids: List[str], filters: ProfileFilters, random_index: float, direction: int) -> Optional[Profile]: pass
    
    @abstractmethod
    async def get_all_by_user(self, user_id: int) -> List[Profile]: pass
    
    @abstractmethod
    async def get_all_missing_random_index(self) -> List[Profile]: pass


class IContactRequestRepository(ABC):
    @abstractmethod
    async def create(self, request_model: ContactRequestModel) -> None: pass
    
    @abstractmethod
    async def get_by_req_id(self, req_id: str) -> Optional[ContactRequestModel]: pass
    
    @abstractmethod
    async def get_pending_by_initiator_target_action(self, initiator_id: int, target_id: int, action: str) -> Optional[ContactRequestModel]: pass
    
    @abstractmethod
    async def update(self, request_model: ContactRequestModel) -> None: pass
    
    @abstractmethod
    async def count_pending_by_initiator(self, initiator_id: int) -> int: pass
    
    @abstractmethod
    async def count_pending_by_target(self, target_id: int) -> int: pass
    
    @abstractmethod
    async def get_pending_actions(self, initiator_id: int, target_id: int) -> List[str]: pass
    
    @abstractmethod
    async def get_pending_by_initiator(self, initiator_id: int) -> List[ContactRequestModel]: pass
    
    @abstractmethod
    async def get_pending_by_target(self, target_id: int) -> List[ContactRequestModel]: pass


class ITagRepository(ABC):
    @abstractmethod
    async def get_by_ids(self, tag_ids: List[str]) -> List[Tag]: pass
    
    @abstractmethod
    async def search(self, query: str, limit: int = 50) -> List[Tag]: pass


class IAlbumRepository(ABC):
    @abstractmethod
    async def is_processed(self, media_group_id: str) -> bool: pass
    
    @abstractmethod
    async def mark_processed(self, media_group_id: str) -> None: pass
    
    @abstractmethod
    async def add_to_buffer(self, media_group_id: str, media_item: MediaItem) -> List[MediaItem]: pass
    
    @abstractmethod
    async def get_and_clear_buffer(self, media_group_id: str) -> List[MediaItem]: pass
    
    @abstractmethod
    async def clear_buffer(self, media_group_id: str) -> None: pass