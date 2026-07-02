from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List
from core.config import AVAILABLE_TAGS
from core.security import validate_webapp_data
from core.database import Database
import os

router = APIRouter()

class UpdateTagsPayload(BaseModel):
    initData: str
    tags: List[str]
    mode: str

@router.get("/webapp", response_class=HTMLResponse)
async def serve_webapp():
    path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@router.get("/api/tags")
async def get_tags():
    return {"tags": AVAILABLE_TAGS}

@router.post("/api/update")
async def update_profile(payload: UpdateTagsPayload):
    user_data = validate_webapp_data(payload.initData)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid InitData")
        
    user_id = user_data['id']
    
    if payload.mode == "edit":
        score_addition = len(payload.tags) # Basic score logic
        await Database.db.profiles.update_one(
            {"user_id": user_id}, 
            {"$set": {"tags": payload.tags}, "$inc": {"score": score_addition}}
        )
        return {"status": "ok", "message": "Profile updated!"}
        
    elif payload.mode == "filter":
        # Save to search cache for this user
        await Database.db.search_sessions.update_one(
            {"user_id": user_id},
            {"$set": {"filters": payload.tags, "cursor_idx": 0}},
            upsert=True
        )
        return {"status": "ok", "message": "Filters applied!"}