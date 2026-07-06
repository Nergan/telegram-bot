from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple

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
    async def get_by_uuid(self, public_uuid: str) -> Optional[Dict[str, Any]]: pass
    
    @abstractmethod
    async def get_active_by_user(self, user_id: int) -> Optional[Dict[str, Any]]: pass
    
    @abstractmethod
    async def count_by_user(self, user_id: int) -> int: pass
    
    @abstractmethod
    async def create(self, profile: Dict[str, Any]) -> Dict[str, Any]: pass
    
    @abstractmethod
    async def update(self, public_uuid: str, update_data: Dict[str, Any]) -> None: pass
    
    @abstractmethod
    async def update_by_id(self, _id: Any, update_data: Dict[str, Any]) -> None: pass
    
    @abstractmethod
    async def update_many_by_user(self, user_id: int, update_data: Dict[str, Any]) -> None: pass
    
    @abstractmethod
    async def delete(self, user_id: int, public_uuid: str) -> None: pass
    
    @abstractmethod
    async def delete_many(self, query: Dict[str, Any]) -> None: pass
    
    @abstractmethod
    async def get_last_by_user(self, user_id: int) -> Optional[Dict[str, Any]]: pass
    
    @abstractmethod
    async def get_pool_size(self, user_id: int, filters: Optional[Dict[str, Any]] = None) -> int: pass
    
    @abstractmethod
    async def find_one_matching(self, query: Dict[str, Any], sort_args: List[Tuple[str, int]]) -> Optional[Dict[str, Any]]: pass
    
    @abstractmethod
    async def get_all_by_user(self, user_id: int) -> List[Dict[str, Any]]: pass
    
    @abstractmethod
    async def get_all_missing_random_index(self) -> List[Dict[str, Any]]: pass


class IContactRequestRepository(ABC):
    @abstractmethod
    async def create(self, request_doc: Dict[str, Any]) -> None: pass
    
    @abstractmethod
    async def get_by_req_id(self, req_id: str) -> Optional[Dict[str, Any]]: pass
    
    @abstractmethod
    async def get_pending_by_initiator_target_action(self, initiator_id: int, target_id: int, action: str) -> Optional[Dict[str, Any]]: pass
    
    @abstractmethod
    async def update_status(self, req_id: str, status: str, extra_data: Optional[Dict[str, Any]] = None) -> None: pass
    
    @abstractmethod
    async def count_pending_by_initiator(self, initiator_id: int) -> int: pass
    
    @abstractmethod
    async def count_pending_by_target(self, target_id: int) -> int: pass
    
    @abstractmethod
    async def get_pending_actions(self, initiator_id: int, target_id: int) -> List[str]: pass
    
    @abstractmethod
    async def get_pending_by_initiator(self, initiator_id: int) -> List[Dict[str, Any]]: pass
    
    @abstractmethod
    async def get_pending_by_target(self, target_id: int) -> List[Dict[str, Any]]: pass


class ITagRepository(ABC):
    @abstractmethod
    async def get_by_ids(self, tag_ids: List[str]) -> List[Dict[str, Any]]: pass
    
    @abstractmethod
    async def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]: pass