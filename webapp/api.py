import os
import html
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from domain.interfaces import INotificationService, ISecurityService
from application.locales import _
from application.services import UserService, ProfileService, TagService, ContactRequestService

router = APIRouter()
logger = logging.getLogger(__name__)

def get_user_svc(request: Request) -> UserService: return request.app.state.user_service
def get_profile_svc(request: Request) -> ProfileService: return request.app.state.profile_service
def get_tag_svc(request: Request) -> TagService: return request.app.state.tag_service
def get_req_svc(request: Request) -> ContactRequestService: return request.app.state.contact_req_service
def get_notif_svc(request: Request) -> INotificationService: return request.app.state.notification_service
def get_security_svc(request: Request) -> ISecurityService: return request.app.state.security_service

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
    tag_service: TagService = Depends(get_tag_svc),
    security_service: ISecurityService = Depends(get_security_svc)
):
    user_data = security_service.validate_webapp_data(payload.initData)
    if not user_data: raise HTTPException(status_code=401)
    if await user_service.is_banned(user_data['id']): raise HTTPException(status_code=403, detail="Banned")
    
    p = await profile_service.get_profile_by_uuid(payload.profile_id)
    if not p: raise HTTPException(status_code=404)
    if p.user_id != user_data['id']: raise HTTPException(status_code=403, detail="Access denied")
    
    active_tags_data = await tag_service.get_tags_by_ids(p.tags)
    active_tags = [{"id": t._id, "display": t.display} for t in active_tags_data]
    
    f_data = p.filters
    req_tags_data = await tag_service.get_tags_by_ids(f_data.require_tags)
    exc_tags_data = await tag_service.get_tags_by_ids(f_data.exclude_tags)
    any_tags_data = await tag_service.get_tags_by_ids(f_data.any_tags)
    
    return {
        "tags": active_tags, 
        "filters": {
            "require_tags": [{"id": t._id, "display": t.display} for t in req_tags_data],
            "exclude_tags": [{"id": t._id, "display": t.display} for t in exc_tags_data],
            "any_tags": [{"id": t._id, "display": t.display} for t in any_tags_data]
        }
    }

@router.post("/api/search_tags")
async def search_tags_endpoint(
    payload: TagSearchPayload, 
    user_service: UserService = Depends(get_user_svc),
    tag_service: TagService = Depends(get_tag_svc),
    security_service: ISecurityService = Depends(get_security_svc)
):
    user_data = security_service.validate_webapp_data(payload.initData)
    if not user_data: raise HTTPException(status_code=401)
    if await user_service.is_banned(user_data['id']): raise HTTPException(status_code=403, detail="Banned")
    
    tags = await tag_service.search_tags(payload.query, limit=50)
    formatted_tags = [{"id": t._id, "display": t.display} for t in tags]
    return {"tags": formatted_tags}

@router.post("/api/update")
async def update_tags(
    payload: WebAppPayload,
    user_service: UserService = Depends(get_user_svc),
    profile_service: ProfileService = Depends(get_profile_svc),
    security_service: ISecurityService = Depends(get_security_svc),
    notif_svc: INotificationService = Depends(get_notif_svc)
):
    user_data = security_service.validate_webapp_data(payload.initData)
    if not user_data: raise HTTPException(status_code=401)
    
    user_id = user_data['id']
    if await user_service.is_banned(user_id): raise HTTPException(status_code=403, detail="Banned")
    
    p = await profile_service.get_profile_by_uuid(payload.profile_id)
    if not p or p.user_id != user_id: 
        raise HTTPException(status_code=403, detail="Access denied")
    
    lang = await user_service.get_lang(user_id)
    
    if payload.mode == "edit":
        p.tags = payload.tags
        await profile_service.update_profile(p)
        msg = "✅ Tags successfully updated!" if lang == "en" else "✅ Tags atualizadas com sucesso!" if lang == "pt" else "✅ Теги успешно обновлены!"
        try: await notif_svc.notify_text(user_id, msg)
        except Exception: pass
    else:
        p.filters.require_tags = payload.require_tags
        p.filters.exclude_tags = payload.exclude_tags
        p.filters.any_tags = payload.any_tags
        await profile_service.update_profile(p)
        msg = "✅ Filters successfully updated!" if lang == "en" else "✅ Filtros atualizados com sucesso!" if lang == "pt" else "✅ Фильтры успешно обновлены!"
        try: await notif_svc.notify_text(user_id, msg)
        except Exception: pass
        
    return {"status": "ok"}

@router.post("/api/get_requests")
async def get_requests_endpoint(
    payload: RequestsPayload,
    user_service: UserService = Depends(get_user_svc),
    profile_service: ProfileService = Depends(get_profile_svc),
    tag_service: TagService = Depends(get_tag_svc),
    contact_req_service: ContactRequestService = Depends(get_req_svc),
    security_service: ISecurityService = Depends(get_security_svc)
):
    try:
        user_data = security_service.validate_webapp_data(payload.initData)
        if not user_data: raise HTTPException(status_code=401)
            
        user_id = user_data['id']
        if await user_service.is_banned(user_id): raise HTTPException(status_code=403, detail="Banned")
            
        my_active = await profile_service.get_active_profile(user_id)
        my_private_contacts = [{"id": c.id, "value": c.value} for c in my_active.contacts if not c.is_public] if my_active else []
            
        sent_list = await contact_req_service.get_pending_by_initiator(user_id)
        recv_list = await contact_req_service.get_pending_by_target(user_id)
        
        async def format_requests(req_list, target_key):
            formatted = []
            for r in req_list:
                uid = getattr(r, target_key)
                if not uid: continue
                other_profile = await profile_service.get_active_profile(uid)
                if not other_profile: continue
                
                tags_data = await tag_service.get_tags_by_ids(other_profile.tags)
                formatted_tags = [{"id": t._id, "display": t.display} for t in tags_data]
                    
                formatted.append({
                    "req_id": r.req_id, "action": r.action,
                    "status": "pending", "message": r.message or "",
                    "shared_contacts": r.shared_contacts,
                    "other_profile": {
                        "public_uuid": other_profile.public_uuid,
                        "bio": other_profile.text or "",
                        "tags": formatted_tags,
                        "public_contacts": [c.value for c in other_profile.contacts if c.is_public],
                        "media_count": len(other_profile.media)
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
    contact_req_service: ContactRequestService = Depends(get_req_svc),
    security_service: ISecurityService = Depends(get_security_svc),
    notif_svc: INotificationService = Depends(get_notif_svc)
):
    try:
        user_data = security_service.validate_webapp_data(payload.initData)
        if not user_data: raise HTTPException(status_code=401)
            
        user_id = user_data['id']
        if await user_service.is_banned(user_id): raise HTTPException(status_code=403, detail="Banned")
            
        req = await contact_req_service.get_request(payload.req_id)
        if not req: raise HTTPException(status_code=404, detail="Request not found")
            
        init_lang = await user_service.get_lang(req.initiator_id)
        tgt_lang = await user_service.get_lang(user_id)
            
        if payload.action == "decline":
            if req.target_id != user_id or req.status != 'pending': raise HTTPException(status_code=403)
            await contact_req_service.update_status(payload.req_id, "declined")
            try: await notif_svc.notify_text(req.initiator_id, _("mut_declined", init_lang))
            except Exception: pass
            return {"status": "ok"}
            
        elif payload.action == "viewed":
            if req.target_id != user_id or req.status != 'pending': raise HTTPException(status_code=403)
            await contact_req_service.update_status(payload.req_id, "viewed")
            return {"status": "ok"}
            
        elif payload.action == "accept":
            if req.target_id != user_id or req.status != 'pending': raise HTTPException(status_code=403)
            if not payload.selected_contact_ids: raise HTTPException(status_code=400)
                
            active_prof = await profile_service.get_active_profile(user_id)
            if not active_prof: raise HTTPException(status_code=400, detail="You do not have an active profile.")
                
            private_contacts = [c for c in active_prof.contacts if not c.is_public]
            shared_values = [c.value for c in private_contacts if c.id in payload.selected_contact_ids]
            
            if not shared_values:
                raise HTTPException(status_code=400, detail="Invalid contact IDs selected.")
                
            initiator_prof = await profile_service.get_active_profile(req.initiator_id)
            if not initiator_prof:
                raise HTTPException(status_code=400, detail="The other user's profile is no longer active.")
            
            await contact_req_service.update_status(payload.req_id, "accepted", shared_values)
            
            try:
                await notif_svc.notify_profile(req.initiator_id, active_prof, init_lang, custom_prefix=_("lbl_exchanged", init_lang))
                contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in shared_values)
                await notif_svc.notify_text(req.initiator_id, _("mut_accepted", init_lang, contacts_text))
            except Exception as e:
                logger.warning(f"Could not notify initiator {req.initiator_id} of request completion: {e}")
            
            initiator_shared = req.shared_contacts
            if initiator_shared:
                try:
                    await notif_svc.notify_profile(user_id, initiator_prof, tgt_lang, custom_prefix=_("lbl_exchanged", tgt_lang))
                    init_contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in initiator_shared)
                    await notif_svc.notify_text(user_id, _("mut_complete", tgt_lang, init_contacts_text))
                except Exception as e:
                    logger.warning(f"Could not deliver initiator profile/contacts to acceptor {user_id}: {e}")
            else:
                try:
                    await notif_svc.notify_text(user_id, "✅ Exchange complete.")
                except Exception as e:
                    logger.warning(f"Could not notify acceptor {user_id} of completion confirmation: {e}")
            return {"status": "ok"}
            
        raise HTTPException(status_code=400, detail="Invalid action")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error occurred in handle_request_endpoint")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/send_profile_to_chat")
async def send_profile_to_chat_endpoint(
    payload: SendToChatPayload,
    user_service: UserService = Depends(get_user_svc),
    profile_service: ProfileService = Depends(get_profile_svc),
    tag_service: TagService = Depends(get_tag_svc),
    contact_req_service: ContactRequestService = Depends(get_req_svc),
    security_service: ISecurityService = Depends(get_security_svc),
    notif_svc: INotificationService = Depends(get_notif_svc)
):
    try:
        user_data = security_service.validate_webapp_data(payload.initData)
        if not user_data: raise HTTPException(status_code=401)
        
        user_id = user_data['id']
        if await user_service.is_banned(user_id): raise HTTPException(status_code=403, detail="Banned")
        
        req = await contact_req_service.get_request(payload.req_id)
        if not req: raise HTTPException(status_code=404, detail="Request not found")
        
        if user_id not in (req.initiator_id, req.target_id):
            raise HTTPException(status_code=403, detail="Access denied")
        
        target_user_id = req.target_id if req.initiator_id == user_id else req.initiator_id
        profile_to_send = await profile_service.get_active_profile(target_user_id)
        if not profile_to_send: raise HTTPException(status_code=404, detail="Target profile no longer exists.")
        
        lang = await user_service.get_lang(user_id)
        await notif_svc.notify_profile(user_id, profile_to_send, lang)
        
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in send_profile_to_chat")
        raise HTTPException(status_code=500, detail=str(e))