from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from core.config import AVAILABLE_TAGS
from core.security import validate_webapp_data
from core.database import Database
import os

router = APIRouter()

class ProfileDataPayload(BaseModel):
    initData: str
    profile_id: str

class EditTagsPayload(BaseModel):
    initData: str
    mode: str
    profile_id: str
    tags: List[str]

class FilterTagsPayload(BaseModel):
    initData: str
    mode: str
    profile_id: str
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

@router.post("/api/get_profile_data")
async def get_profile_data(payload: ProfileDataPayload):
    """Returns current tags and filters for the UI to pre-load."""
    user_data = validate_webapp_data(payload.initData)
    if not user_data: raise HTTPException(status_code=401)
    
    profile = await Database.get_profile_by_uuid(payload.profile_id)
    if not profile or profile['user_id'] != user_data['id']:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    return {
        "tags": profile.get("tags", []),
        "filters": profile.get("filters", {"require_tags": [], "exclude_tags": [], "any_tags": []})
    }

@router.post("/api/update_edit")
async def update_profile_tags(payload: EditTagsPayload):
    user_data = validate_webapp_data(payload.initData)
    if not user_data: raise HTTPException(status_code=401)
    
    await Database.db.profiles.update_one(
        {"user_id": user_data['id'], "public_uuid": payload.profile_id}, 
        {"$set": {"tags": payload.tags}}
    )
    return {"status": "ok"}

@router.post("/api/update_filter")
async def update_filters(payload: FilterTagsPayload):
    user_data = validate_webapp_data(payload.initData)
    if not user_data: raise HTTPException(status_code=401)
    
    filter_data = {
        "require_tags": payload.require_tags,
        "exclude_tags": payload.exclude_tags,
        "any_tags": payload.any_tags
    }
    
    await Database.db.profiles.update_one(
        {"user_id": user_data['id'], "public_uuid": payload.profile_id},
        {"$set": {"filters": filter_data}}
    )
    return {"status": "ok"}