import os
import html
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from infrastructure.security import validate_webapp_data
from bot.bot_setup import bot
from bot.helpers import send_profile
from infrastructure.locales import _
from application.services import UserService, ProfileService, TagService, ContactRequestService

router = APIRouter()
logger = logging.getLogger(__name__)

# FastAPI Service Dependencies
def get_user_svc(request: Request) -> UserService: return request.app.state.user_service
def get_profile_svc(request: Request) -> ProfileService: return request.app.state.profile_service
def get_tag_svc(request: Request) -> TagService: return request.app.state.tag_service
def get_req_svc(request: Request) -> ContactRequestService: return request.app.state.contact_req_service

class WebAppPayload(BaseModel):
    initData: str
    mode: str
    profile_id: str
    tags: List[str] = Field(default_factory=list)
    require_tags: List[str] = Field(default_factory=list)
    exclude_tags: List[str] = Field(default_factory=list)
    any_tags: List[str] = Field(default_factory=list)

class TagSearchPayload(BaseModel):
    initData: str
    query: str

class RequestsPayload(BaseModel):
    initData: str

class HandleRequestPayload(BaseModel):
    initData: str
    req_id: str
    action: str  
    selected_contact_ids: Optional[List[str]] = None

class SendToChatPayload(BaseModel):
    initData: str
    req_id: str

@router.get("/webapp", response_class=HTMLResponse)
async def serve_webapp():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@router.post("/api/get_profile_data")
async def get_profile_data(
    payload: WebAppPayload, 
    user_service: UserService = Depends(get_user_svc),
    profile_service: ProfileService = Depends(get_profile_svc),
    tag_service: TagService = Depends(get_tag_svc)
):
    user_data = validate_webapp_data(payload.initData)
    if not user_data: raise HTTPException(status_code=401)
    if await user_service.is_banned(user_data['id']): raise HTTPException(status_code=403, detail="Banned")
    
    p = await profile_service.get_profile_by_uuid(payload.profile_id)
    if not p: raise HTTPException(status_code=404)
    
    active_tags_data = await tag_service.get_tags_by_ids(p.get("tags", []))
    active_tags = [{"id": t["_id"], "display": t["display"]} for t in active_tags_data]
    
    f_data = p.get("filters", {})
    req_tags_data = await tag_service.get_tags_by_ids(f_data.get("require_tags", []))
    exc_tags_data = await tag_service.get_tags_by_ids(f_data.get("exclude_tags", []))
    any_tags_data = await tag_service.get_tags_by_ids(f_data.get("any_tags", []))
    
    return {
        "tags": active_tags, 
        "filters": {
            "require_tags": [{"id": t["_id"], "display": t["display"]} for t in req_tags_data],
            "exclude_tags": [{"id": t["_id"], "display": t["display"]} for t in exc_tags_data],
            "any_tags": [{"id": t["_id"], "display": t["display"]} for t in any_tags_data]
        }
    }

@router.post("/api/search_tags")
async def search_tags_endpoint(
    payload: TagSearchPayload, 
    user_service: UserService = Depends(get_user_svc),
    tag_service: TagService = Depends(get_tag_svc)
):
    user_data = validate_webapp_data(payload.initData)
    if not user_data: raise HTTPException(status_code=401)
    if await user_service.is_banned(user_data['id']): raise HTTPException(status_code=403, detail="Banned")
    
    tags = await tag_service.search_tags(payload.query, limit=50)
    formatted_tags = [{"id": t["_id"], "display": t["display"]} for t in tags]
    return {"tags": formatted_tags}

@router.post("/api/update")
async def update_tags(
    payload: WebAppPayload,
    user_service: UserService = Depends(get_user_svc),
    profile_service: ProfileService = Depends(get_profile_svc)
):
    user_data = validate_webapp_data(payload.initData)
    if not user_data: raise HTTPException(status_code=401)
    
    user_id = user_data['id']
    if await user_service.is_banned(user_id): raise HTTPException(status_code=403, detail="Banned")
    
    lang = await user_service.get_lang(user_id)
    
    if payload.mode == "edit":
        await profile_service.update_profile(payload.profile_id, {"tags": payload.tags})
        msg = "✅ Tags successfully updated!" if lang == "en" else "✅ Tags atualizadas com sucesso!" if lang == "pt" else "✅ Теги успешно обновлены!"
        await bot.send_message(user_id, msg)
    else:
        f_data = {"require_tags": payload.require_tags, "exclude_tags": payload.exclude_tags, "any_tags": payload.any_tags}
        await profile_service.update_profile(payload.profile_id, {"filters": f_data})
        msg = "✅ Filters successfully updated!" if lang == "en" else "✅ Filtros atualizados com sucesso!" if lang == "pt" else "✅ Фильтры успешно обновлены!"
        await bot.send_message(user_id, msg)
        
    return {"status": "ok"}

@router.post("/api/get_requests")
async def get_requests_endpoint(
    payload: RequestsPayload,
    user_service: UserService = Depends(get_user_svc),
    profile_service: ProfileService = Depends(get_profile_svc),
    tag_service: TagService = Depends(get_tag_svc),
    contact_req_service: ContactRequestService = Depends(get_req_svc)
):
    try:
        user_data = validate_webapp_data(payload.initData)
        if not user_data: raise HTTPException(status_code=401)
            
        user_id = user_data['id']
        if await user_service.is_banned(user_id): raise HTTPException(status_code=403, detail="Banned")
            
        my_active = await profile_service.get_active_profile(user_id)
        my_private_contacts = [{"id": c["id"], "value": c["value"]} for c in my_active.get("contacts", []) if not c.get("is_public")] if my_active else []
            
        sent_list = await contact_req_service.get_pending_by_initiator(user_id)
        recv_list = await contact_req_service.get_pending_by_target(user_id)
        
        async def format_requests(req_list, target_key):
            formatted = []
            for r in req_list:
                uid = r.get(target_key)
                if not uid: continue
                other_profile = await profile_service.get_active_profile(uid)
                if not other_profile: continue
                
                tags_data = await tag_service.get_tags_by_ids(other_profile.get("tags", []))
                formatted_tags = [{"id": t["_id"], "display": t["display"]} for t in tags_data]
                    
                formatted.append({
                    "req_id": r.get("req_id", ""), "action": r.get("action", "req"),
                    "status": "pending", "message": r.get("message", ""),
                    "shared_contacts": r.get("shared_contacts", []),
                    "other_profile": {
                        "public_uuid": other_profile.get("public_uuid", ""),
                        "bio": other_profile.get("text", "") or "",
                        "tags": formatted_tags,
                        "public_contacts": [c.get("value", "") for c in other_profile.get("contacts", []) if c.get("is_public")],
                        "media_count": len(other_profile.get("media", []))
                    }
                })
            return formatted

        return {
            "sent_requests": await format_requests(sent_list, 'target_id'),
            "received_requests": await format_requests(recv_list, 'initiator_id'),
            "my_private_contacts": my_private_contacts
        }
    except Exception as e:
        logger.exception("Error occurred in get_requests_endpoint")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/handle_request")
async def handle_request_endpoint(
    payload: HandleRequestPayload,
    user_service: UserService = Depends(get_user_svc),
    profile_service: ProfileService = Depends(get_profile_svc),
    tag_service: TagService = Depends(get_tag_svc),
    contact_req_service: ContactRequestService = Depends(get_req_svc)
):
    try:
        user_data = validate_webapp_data(payload.initData)
        if not user_data: raise HTTPException(status_code=401)
            
        user_id = user_data['id']
        if await user_service.is_banned(user_id): raise HTTPException(status_code=403, detail="Banned")
            
        req = await contact_req_service.get_request(payload.req_id)
        if not req: raise HTTPException(status_code=404, detail="Request not found")
            
        init_lang = await user_service.get_lang(req['initiator_id'])
        tgt_lang = await user_service.get_lang(user_id)
            
        if payload.action == "decline":
            if req['target_id'] != user_id or req['status'] != 'pending': raise HTTPException(status_code=403)
            await contact_req_service.update_status(payload.req_id, "declined")
            try: await bot.send_message(req['initiator_id'], _("mut_declined", init_lang))
            except Exception: pass
            return {"status": "ok"}
            
        elif payload.action == "viewed":
            if req['target_id'] != user_id or req['status'] != 'pending': raise HTTPException(status_code=403)
            await contact_req_service.update_status(payload.req_id, "viewed")
            return {"status": "ok"}
            
        elif payload.action == "accept":
            if req['target_id'] != user_id or req['status'] != 'pending': raise HTTPException(status_code=403)
            if not payload.selected_contact_ids: raise HTTPException(status_code=400)
                
            active_prof = await profile_service.get_active_profile(user_id)
            if not active_prof: raise HTTPException(status_code=400)
                
            private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
            shared_values = [c["value"] for c in private_contacts if c["id"] in payload.selected_contact_ids]
            
            await contact_req_service.update_status(payload.req_id, "accepted", {"target_shared_contacts": shared_values})
            
            b_profile = await profile_service.get_active_profile(user_id)
            await send_profile(req['initiator_id'], b_profile, None, init_lang, tag_service, custom_prefix=_("lbl_exchanged", init_lang))
            
            contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in shared_values)
            await bot.send_message(req['initiator_id'], _("mut_accepted", init_lang, contacts_text))
            
            initiator_shared = req.get("shared_contacts", [])
            if initiator_shared:
                a_profile = await profile_service.get_active_profile(req['initiator_id'])
                await send_profile(user_id, a_profile, None, tgt_lang, tag_service, custom_prefix=_("lbl_exchanged", tgt_lang))
                init_contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in initiator_shared)
                await bot.send_message(user_id, _("mut_complete", tgt_lang, init_contacts_text))
            else:
                await bot.send_message(user_id, "✅ Exchange complete.")
            return {"status": "ok"}
            
        raise HTTPException(status_code=400, detail="Invalid action")
    except Exception as e:
        logger.exception("Error occurred in handle_request_endpoint")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/send_profile_to_chat")
async def send_profile_to_chat_endpoint(
    payload: SendToChatPayload,
    user_service: UserService = Depends(get_user_svc),
    profile_service: ProfileService = Depends(get_profile_svc),
    tag_service: TagService = Depends(get_tag_svc),
    contact_req_service: ContactRequestService = Depends(get_req_svc)
):
    try:
        user_data = validate_webapp_data(payload.initData)
        if not user_data: raise HTTPException(status_code=401)
        
        user_id = user_data['id']
        if await user_service.is_banned(user_id): raise HTTPException(status_code=403, detail="Banned")
        
        req = await contact_req_service.get_request(payload.req_id)
        if not req: raise HTTPException(status_code=404, detail="Request not found")
        
        target_user_id = req['target_id'] if req['initiator_id'] == user_id else req['initiator_id']
        profile_to_send = await profile_service.get_active_profile(target_user_id)
        if not profile_to_send: raise HTTPException(status_code=404, detail="Target profile no longer exists.")
        
        lang = await user_service.get_lang(user_id)
        await send_profile(user_id, profile_to_send, None, lang, tag_service)
        
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in send_profile_to_chat")
        raise HTTPException(status_code=500, detail=str(e))