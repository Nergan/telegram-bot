import os
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from core.config import AVAILABLE_TAGS
from core.security import validate_webapp_data
from core.database import Database
from bot.bot_setup import bot
from bot.keyboards import profile_inline_kb  # Оставляем только нужный импорт
from bot.helpers import send_profile

router = APIRouter()

class WebAppPayload(BaseModel):
    initData: str
    mode: str
    profile_id: str
    tags: List[str] = Field(default_factory=list)
    require_tags: List[str] = Field(default_factory=list)
    exclude_tags: List[str] = Field(default_factory=list)
    any_tags: List[str] = Field(default_factory=list)

@router.get("/webapp", response_class=HTMLResponse)
async def serve_webapp():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), "r", encoding="utf-8") as f:
        html = f.read()
    return html.replace("{{AVAILABLE_TAGS_JSON}}", json.dumps(AVAILABLE_TAGS))

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
        
    active = await Database.get_active_profile(user_id)
    if active and active['public_uuid'] == payload.profile_id:
        # Убрано служебное текстовое сообщение "Settings updated!"
        # Сразу отправляем обновленную анкету с новыми inline-кнопками тегов/фильтров
        await send_profile(user_id, active, profile_inline_kb(active['public_uuid']))
        
    return {"status": "ok"}