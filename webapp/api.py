import os
import json
import html
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from core.config import AVAILABLE_TAGS
from core.security import validate_webapp_data
from core.database import Database
from bot.bot_setup import bot
from bot.helpers import send_profile
from core.locales import _

router = APIRouter()
logger = logging.getLogger(__name__)

class WebAppPayload(BaseModel):
    initData: str
    mode: str
    profile_id: str
    tags: List[str] = Field(default_factory=list)
    require_tags: List[str] = Field(default_factory=list)
    exclude_tags: List[str] = Field(default_factory=list)
    any_tags: List[str] = Field(default_factory=list)

class RequestsPayload(BaseModel):
    initData: str

class HandleRequestPayload(BaseModel):
    initData: str
    req_id: str
    action: str  # "accept", "decline", "viewed"
    selected_contact_ids: Optional[List[str]] = None

@router.get("/webapp", response_class=HTMLResponse)
async def serve_webapp():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), "r", encoding="utf-8") as f:
        html_content = f.read()
    return html_content.replace("{{AVAILABLE_TAGS_JSON}}", json.dumps(AVAILABLE_TAGS))

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
    lang = await Database.get_user_lang(user_id)
    
    if payload.mode == "edit":
        await Database.db.profiles.update_one({"user_id": user_id, "public_uuid": payload.profile_id}, {"$set": {"tags": payload.tags}})
        active = await Database.get_active_profile(user_id)
        if active and active['public_uuid'] == payload.profile_id:
            if lang == "en":
                msg = "✅ Tags successfully updated!"
            elif lang == "pt":
                msg = "✅ Tags atualizadas com sucesso!"
            else:
                msg = "✅ Теги успешно обновлены!"
            await bot.send_message(user_id, msg)
    else:
        f_data = {"require_tags": payload.require_tags, "exclude_tags": payload.exclude_tags, "any_tags": payload.any_tags}
        await Database.db.profiles.update_one({"user_id": user_id, "public_uuid": payload.profile_id}, {"$set": {"filters": f_data}})
        active = await Database.get_active_profile(user_id)
        if active and active['public_uuid'] == payload.profile_id:
            if lang == "en":
                msg = "✅ Filters successfully updated!"
            elif lang == "pt":
                msg = "✅ Filtros atualizados com sucesso!"
            else:
                msg = "✅ Фильтры успешно обновлены!"
            await bot.send_message(user_id, msg)
        
    return {"status": "ok"}

@router.post("/api/get_requests")
async def get_requests_endpoint(payload: RequestsPayload):
    try:
        user_data = validate_webapp_data(payload.initData)
        if not user_data:
            raise HTTPException(status_code=401, detail="Unauthorized")
            
        user_id = user_data['id']
        my_active = await Database.get_active_profile(user_id)
        my_private_contacts = []
        if my_active:
            my_private_contacts = [
                {"id": c.get("id", ""), "value": c.get("value", "")} 
                for c in my_active.get("contacts", []) 
                if not c.get("is_public")
            ]
            
        sent_cursor = Database.db.contact_requests.find({"initiator_id": user_id, "status": "pending"})
        sent_list = await sent_cursor.to_list(length=100)
        
        recv_cursor = Database.db.contact_requests.find({"target_id": user_id, "status": "pending"})
        recv_list = await recv_cursor.to_list(length=100)
        
        formatted_sent = []
        for r in sent_list:
            target_id = r.get('target_id')
            if not target_id: continue
            other_profile = await Database.get_active_profile(target_id)
            if not other_profile: continue
                
            formatted_sent.append({
                "req_id": r.get("req_id", ""),
                "action": r.get("action", "req"),
                "status": "pending",
                "message": r.get("message", ""),
                "shared_contacts": r.get("shared_contacts", []),
                "other_profile": {
                    "public_uuid": other_profile.get("public_uuid", ""),
                    "bio": other_profile.get("text", "") or "",
                    "tags": other_profile.get("tags", []),
                    "public_contacts": [c.get("value", "") for c in other_profile.get("contacts", []) if c.get("is_public")]
                }
            })
            
        formatted_recv = []
        for r in recv_list:
            initiator_id = r.get('initiator_id')
            if not initiator_id: continue
            other_profile = await Database.get_active_profile(initiator_id)
            if not other_profile: continue
                
            formatted_recv.append({
                "req_id": r.get("req_id", ""),
                "action": r.get("action", "req"),
                "status": "pending",
                "message": r.get("message", ""),
                "shared_contacts": r.get("shared_contacts", []),
                "other_profile": {
                    "public_uuid": other_profile.get("public_uuid", ""),
                    "bio": other_profile.get("text", "") or "",
                    "tags": other_profile.get("tags", []),
                    "public_contacts": [c.get("value", "") for c in other_profile.get("contacts", []) if c.get("is_public")]
                }
            })
            
        return {
            "sent_requests": formatted_sent,
            "received_requests": formatted_recv,
            "my_private_contacts": my_private_contacts
        }
    except Exception as e:
        logger.exception("Error occurred in get_requests_endpoint")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/handle_request")
async def handle_request_endpoint(payload: HandleRequestPayload):
    try:
        user_data = validate_webapp_data(payload.initData)
        if not user_data:
            raise HTTPException(status_code=401, detail="Unauthorized")
            
        user_id = user_data['id']
        req = await Database.db.contact_requests.find_one({"req_id": payload.req_id})
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
            
        init_lang = await Database.get_user_lang(req['initiator_id'])
        tgt_lang = await Database.get_user_lang(user_id)
            
        if payload.action == "decline":
            if req['target_id'] != user_id or req['status'] != 'pending':
                raise HTTPException(status_code=403, detail="Permission denied")
                
            await Database.db.contact_requests.update_one({"req_id": payload.req_id}, {"$set": {"status": "declined"}})
            
            try:
                await bot.send_message(req['initiator_id'], _("mut_declined", init_lang))
            except Exception:
                pass
            return {"status": "ok"}
            
        elif payload.action == "viewed":
            if req['target_id'] != user_id or req['status'] != 'pending':
                raise HTTPException(status_code=403, detail="Permission denied")
                
            await Database.db.contact_requests.update_one({"req_id": payload.req_id}, {"$set": {"status": "viewed"}})
            return {"status": "ok"}
            
        elif payload.action == "accept":
            if req['target_id'] != user_id or req['status'] != 'pending':
                raise HTTPException(status_code=403, detail="Permission denied")
                
            if not payload.selected_contact_ids:
                raise HTTPException(status_code=400, detail="Missing selected contacts")
                
            active_prof = await Database.get_active_profile(user_id)
            if not active_prof:
                raise HTTPException(status_code=400, detail="Active profile not found")
                
            private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
            shared_values = [c["value"] for c in private_contacts if c["id"] in payload.selected_contact_ids]
            
            await Database.db.contact_requests.update_one(
                {"req_id": payload.req_id}, 
                {"$set": {"status": "accepted", "target_shared_contacts": shared_values}}
            )
            
            b_profile = await Database.get_active_profile(user_id)
            await send_profile(req['initiator_id'], b_profile, None, init_lang, custom_prefix=_("lbl_exchanged", init_lang))
            
            contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in shared_values)
            await bot.send_message(req['initiator_id'], _("mut_accepted", init_lang, contacts_text))
            
            initiator_shared = req.get("shared_contacts", [])
            if initiator_shared:
                a_profile = await Database.get_active_profile(req['initiator_id'])
                await send_profile(user_id, a_profile, None, tgt_lang, custom_prefix=_("lbl_exchanged", tgt_lang))
                
                init_contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in initiator_shared)
                await bot.send_message(user_id, _("mut_complete", tgt_lang, init_contacts_text))
            else:
                await bot.send_message(user_id, "✅ Exchange complete.")
                
            return {"status": "ok"}
            
        raise HTTPException(status_code=400, detail="Invalid action")
    except Exception as e:
        logger.exception("Error occurred in handle_request_endpoint")
        raise HTTPException(status_code=500, detail=str(e))