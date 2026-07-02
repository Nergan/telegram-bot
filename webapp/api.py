from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from core.config import AVAILABLE_TAGS
from core.security import validate_webapp_data
from core.database import Database
import os

router = APIRouter()

class EditTagsPayload(BaseModel):
    initData: str
    mode: str
    profile_id: Optional[str] = None
    tags: List[str]  # Just an array for Edit mode

class FilterTagsPayload(BaseModel):
    initData: str
    mode: str
    require_tags: List[str]
    exclude_tags: List[str]
    any_tags: List[str]

@router.get("/webapp", response_class=HTMLResponse)
async def serve_webapp():
    path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@router.get("/api/tags")
async def get_tags():
    return {"tags": AVAILABLE_TAGS}

@router.post("/api/update_edit")
async def update_profile_tags(payload: EditTagsPayload):
    user_data = validate_webapp_data(payload.initData)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid InitData")
        
    user_id = user_data['id']
    await Database.log_action(user_id, "webapp_edit_tags", {"profile_id": payload.profile_id, "tags": payload.tags})
    
    await Database.db.profiles.update_one(
        {"user_id": user_id, "public_uuid": payload.profile_id}, 
        {"$set": {"tags": payload.tags}}
    )
    return {"status": "ok"}

@router.post("/api/update_filter")
async def update_filters(payload: FilterTagsPayload):
    user_data = validate_webapp_data(payload.initData)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid InitData")
        
    user_id = user_data['id']
    filter_data = {
        "require_tags": payload.require_tags,
        "exclude_tags": payload.exclude_tags,
        "any_tags": payload.any_tags
    }
    await Database.log_action(user_id, "webapp_update_filters", filter_data)
    
    await Database.db.search_sessions.update_one(
        {"user_id": user_id},
        {"$set": {"filters": filter_data}},
        upsert=True
    )
    return {"status": "ok"}