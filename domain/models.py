import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class Contact:
    id: str
    type: str
    value: str
    is_public: bool

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "type": self.type, "value": self.value, "is_public": self.is_public}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Contact":
        return cls(id=d.get("id", ""), type=d.get("type", ""), value=d.get("value", ""), is_public=d.get("is_public", False))


@dataclass
class ProfileFilters:
    require_tags: List[str] = field(default_factory=list)
    exclude_tags: List[str] = field(default_factory=list)
    any_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"require_tags": self.require_tags, "exclude_tags": self.exclude_tags, "any_tags": self.any_tags}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProfileFilters":
        if not d: return cls()
        return cls(require_tags=d.get("require_tags", []), exclude_tags=d.get("exclude_tags", []), any_tags=d.get("any_tags", []))


@dataclass
class MediaItem:
    type: str
    file_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = {"type": self.type}
        if self.file_id: res["file_id"] = self.file_id
        return res

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MediaItem":
        return cls(type=d.get("type", ""), file_id=d.get("file_id"))


@dataclass
class Profile:
    user_id: int
    public_uuid: str
    is_active: bool
    random_index: float
    created_at: datetime.datetime
    _id: Any = None
    username: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    filters: ProfileFilters = field(default_factory=ProfileFilters)
    contacts: List[Contact] = field(default_factory=list)
    text: Optional[str] = None
    media: List[MediaItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "user_id": self.user_id,
            "public_uuid": self.public_uuid,
            "is_active": self.is_active,
            "random_index": self.random_index,
            "created_at": self.created_at,
            "username": self.username,
            "tags": self.tags,
            "filters": self.filters.to_dict(),
            "contacts": [c.to_dict() for c in self.contacts],
            "text": self.text,
            "media": [m.to_dict() for m in self.media]
        }
        if self._id is not None: d["_id"] = self._id
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Optional["Profile"]:
        if not d: return None
        return cls(
            user_id=d.get("user_id", 0),
            public_uuid=d.get("public_uuid", ""),
            is_active=d.get("is_active", False),
            random_index=d.get("random_index", 0.0),
            created_at=d.get("created_at", datetime.datetime.now(datetime.timezone.utc)),
            _id=d.get("_id"),
            username=d.get("username"),
            tags=d.get("tags", []),
            filters=ProfileFilters.from_dict(d.get("filters", {})),
            contacts=[Contact.from_dict(c) for c in d.get("contacts", [])],
            text=d.get("text"),
            media=[MediaItem.from_dict(m) for m in d.get("media", [])]
        )


@dataclass
class ContactRequestModel:
    req_id: str
    initiator_id: int
    target_id: int
    action: str
    status: str
    message: Optional[str] = None
    shared_contacts: List[str] = field(default_factory=list)
    target_shared_contacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "req_id": self.req_id, "initiator_id": self.initiator_id, "target_id": self.target_id,
            "action": self.action, "status": self.status, "message": self.message,
            "shared_contacts": self.shared_contacts, "target_shared_contacts": self.target_shared_contacts
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Optional["ContactRequestModel"]:
        if not d: return None
        return cls(
            req_id=d.get("req_id", ""), initiator_id=d.get("initiator_id", 0), target_id=d.get("target_id", 0),
            action=d.get("action", ""), status=d.get("status", ""), message=d.get("message"),
            shared_contacts=d.get("shared_contacts", []), target_shared_contacts=d.get("target_shared_contacts", [])
        )


@dataclass
class Tag:
    _id: str
    category: str
    display: Dict[str, str]
    search_terms: List[str]
    weight: int
    parent_id: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Optional["Tag"]:
        if not d: return None
        return cls(
            _id=d.get("_id", ""), category=d.get("category", ""), display=d.get("display", {}),
            search_terms=d.get("search_terms", []), weight=d.get("weight", 0), parent_id=d.get("parent_id")
        )