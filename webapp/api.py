from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from core.config import AVAILABLE_TAGS
from core.security import validate_webapp_data
from core.database import Database
from bot.bot_setup import bot
from bot.keyboards import dashboard_kb
from bot.helpers import send_profile
import os
from fastapi.responses import HTMLResponse

router = APIRouter()

class WebAppPayload(BaseModel):
    initData: str; mode: str; profile_id: str; tags: Optional[List[str]] = None
    require_tags: Optional[List[str]] = None; exclude_tags: Optional[List[str]] = None; any_tags: Optional[List[str]] = None

@router.get("/webapp", response_class=HTMLResponse)
async def serve_webapp():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@router.get("/api/tags")
async def get_tags(): return {"tags": AVAILABLE_TAGS}

@router.post("/api/get_profile_data")
async def get_profile_data(payload: WebAppPayload):
    user_data = validate_webapp_data(payload.initData)
    if not user_data: raise HTTPException(status_code=401)
    p = await Database.get_profile_by_uuid(payload.profile_id)
    return {"tags": p.get("tags", []), "filters": p.get("filters", {})}

@router.post("/api/update")
async def update_tags(payload: WebAppPayload):
    user_data = validate_webapp_data(payload.initData)
    if not user_data: raise HTTPException(status_code=401)
    
    user_id = user_data['id']
    if payload.mode == "edit":
        await Database.db.profiles.update_one({"user_id": user_id, "public_uuid": payload.profile_id}, {"$set": {"tags": payload.tags}})
    else:
        f_data = {"require_tags": payload.require_tags, "exclude_tags": payload.exclude_tags, "any_tags": payload.any_tags}
        await Database.db.profiles.update_one({"user_id": user_id, "public_uuid": payload.profile_id}, {"$set": {"filters": f_data}})
        
    # IMMEDIATE UPDATE: Send fresh dashboard
    active = await Database.get_active_profile(user_id)
    if active and active['public_uuid'] == payload.profile_id:
        await bot.send_message(user_id, "✅ Settings updated from WebApp!")
        await send_profile(user_id, active, dashboard_kb(active['public_uuid']), is_dashboard=True)
        
    return {"status": "ok"}