import os
import json
import html
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from core.config import AVAILABLE_TAGS
from core.security import validate_webapp_data
from core.database import Database
from bot.bot_setup import bot
from bot.keyboards import profile_inline_kb, mutual_exchange_kb  
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

class RequestsPayload(BaseModel):
    initData: str

class HandleRequestPayload(BaseModel):
    initData: str
    req_id: str
    action: str  # "accept", "decline", "cancel", "counter", "agree_exchange"
    selected_contact_ids: Optional[List[str]] = None

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
        active = await Database.get_active_profile(user_id)
        if active and active['public_uuid'] == payload.profile_id:
            await bot.send_message(user_id, "✅ Tags successfully updated!")
    else:
        f_data = {"require_tags": payload.require_tags, "exclude_tags": payload.exclude_tags, "any_tags": payload.any_tags}
        await Database.db.profiles.update_one({"user_id": user_id, "public_uuid": payload.profile_id}, {"$set": {"filters": f_data}})
        active = await Database.get_active_profile(user_id)
        if active and active['public_uuid'] == payload.profile_id:
            await bot.send_message(user_id, "✅ Filters successfully updated!")
        
    return {"status": "ok"}

@router.post("/api/get_requests")
async def get_requests_endpoint(payload: RequestsPayload):
    user_data = validate_webapp_data(payload.initData)
    if not user_data:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    user_id = user_data['id']
    my_active = await Database.get_active_profile(user_id)
    my_private_contacts = []
    if my_active:
        my_private_contacts = [
            {"id": c["id"], "value": c["value"]} 
            for c in my_active.get("contacts", []) 
            if not c.get("is_public")
        ]
        
    sent_cursor = Database.db.contact_requests.find({"initiator_id": user_id})
    sent_list = await sent_cursor.to_list(length=100)
    
    recv_cursor = Database.db.contact_requests.find({"target_id": user_id})
    recv_list = await recv_cursor.to_list(length=100)
    
    formatted_sent = []
    for r in sent_list:
        other_profile = await Database.get_active_profile(r['target_id'])
        if not other_profile:
            continue
            
        disclosed_contacts = []
        if r['status'] == 'accepted':
            disclosed_contacts = r.get("target_shared_contacts", r.get("counter_shared_contacts", []))
            
        formatted_sent.append({
            "req_id": r["req_id"],
            "status": r["status"],
            "message": r.get("message", ""),
            "action": r.get("action", ""),
            "shared_contacts": r.get("shared_contacts", []),
            "counter_shared_contacts": r.get("counter_shared_contacts", []),
            "initiator_shared_contacts": r.get("initiator_shared_contacts", []),
            "other_profile": {
                "public_uuid": other_profile["public_uuid"],
                "bio": other_profile.get("text", "") or "",
                "tags": other_profile.get("tags", []),
                "public_contacts": [c["value"] for c in other_profile.get("contacts", []) if c.get("is_public")]
            },
            "disclosed_contacts": disclosed_contacts
        })
        
    formatted_recv = []
    for r in recv_list:
        other_profile = await Database.get_active_profile(r['initiator_id'])
        if not other_profile:
            continue
            
        disclosed_contacts = []
        if r['status'] == 'accepted':
            disclosed_contacts = r.get("shared_contacts", []) or r.get("initiator_shared_contacts", [])
            
        formatted_recv.append({
            "req_id": r["req_id"],
            "status": r["status"],
            "message": r.get("message", ""),
            "action": r.get("action", ""),
            "shared_contacts": r.get("shared_contacts", []),
            "counter_shared_contacts": r.get("counter_shared_contacts", []),
            "initiator_shared_contacts": r.get("initiator_shared_contacts", []),
            "other_profile": {
                "public_uuid": other_profile["public_uuid"],
                "bio": other_profile.get("text", "") or "",
                "tags": other_profile.get("tags", []),
                "public_contacts": [c["value"] for c in other_profile.get("contacts", []) if c.get("is_public")]
            },
            "disclosed_contacts": disclosed_contacts
        })
        
    return {
        "sent_requests": formatted_sent,
        "received_requests": formatted_recv,
        "my_private_contacts": my_private_contacts
    }

@router.post("/api/handle_request")
async def handle_request_endpoint(payload: HandleRequestPayload):
    user_data = validate_webapp_data(payload.initData)
    if not user_data:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    user_id = user_data['id']
    req = await Database.db.contact_requests.find_one({"req_id": payload.req_id})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    if payload.action == "cancel":
        if req['initiator_id'] != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        if req['status'] not in ['pending', 'counter_pending']:
            raise HTTPException(status_code=400, detail="Cannot cancel this request")
            
        await Database.db.contact_requests.delete_one({"req_id": payload.req_id})
        return {"status": "ok"}
        
    elif payload.action == "decline":
        is_allowed = False
        if req['status'] == 'pending' and req['target_id'] == user_id:
            is_allowed = True
        elif req['status'] == 'counter_pending' and req['initiator_id'] == user_id:
            is_allowed = True
            
        if not is_allowed:
            raise HTTPException(status_code=403, detail="Permission denied or invalid status")
            
        await Database.db.contact_requests.update_one({"req_id": payload.req_id}, {"$set": {"status": "declined"}})
        
        other_id = req['initiator_id'] if user_id == req['target_id'] else req['target_id']
        try:
            await bot.send_message(other_id, "❌ A contact exchange request was declined.")
        except Exception:
            pass
        return {"status": "ok"}
        
    elif payload.action in ["accept", "counter", "agree_exchange"]:
        if not payload.selected_contact_ids:
            raise HTTPException(status_code=400, detail="You must select at least one contact to share.")
            
        active_prof = await Database.get_active_profile(user_id)
        if not active_prof:
            raise HTTPException(status_code=400, detail="Active profile not found.")
            
        private_contacts = [c for c in active_prof.get("contacts", []) if not c.get("is_public")]
        if not private_contacts:
            raise HTTPException(status_code=400, detail="You have no private contacts to share. Please add one first!")
            
        shared_values = [c["value"] for c in private_contacts if c["id"] in payload.selected_contact_ids]
        if not shared_values:
            raise HTTPException(status_code=400, detail="None of your selected contacts are valid.")
            
        if payload.action == "accept":
            if req['target_id'] != user_id or req['status'] != 'pending':
                raise HTTPException(status_code=403, detail="Permission denied.")
                
            await Database.db.contact_requests.update_one(
                {"req_id": payload.req_id}, 
                {"$set": {"status": "accepted", "target_shared_contacts": shared_values}}
            )
            
            b_profile = await Database.get_active_profile(user_id)
            await send_profile(req['initiator_id'], b_profile, kb=None, custom_prefix="👤 <b>Exchanged Profile:</b>\n\n")
            
            contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in shared_values)
            await bot.send_message(
                req['initiator_id'], 
                f"✅ <b>Request Accepted!</b>\nThe user shared their contact details:\n\n{contacts_text}"
            )
            
            initiator_shared = req.get("shared_contacts", [])
            if initiator_shared:
                a_profile = await Database.get_active_profile(req['initiator_id'])
                await send_profile(user_id, a_profile, kb=None, custom_prefix="👤 <b>Exchanged Profile:</b>\n\n")
                
                init_contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in initiator_shared)
                await bot.send_message(
                    user_id,
                    f"🤝 <b>You shared your contact details.</b>\nHere are the contact details they shared with you:\n\n{init_contacts_text}"
                )
            else:
                await bot.send_message(user_id, "✅ You accepted the request. They received your contact info.")
            return {"status": "ok"}
            
        elif payload.action == "counter":
            if req['target_id'] != user_id or req['status'] != 'pending':
                raise HTTPException(status_code=403, detail="Permission denied.")
                
            initiator_prof = await Database.get_active_profile(req['initiator_id'])
            if not initiator_prof:
                raise HTTPException(status_code=400, detail="Initiator's profile no longer exists.")
                
            initiator_private = [c for c in initiator_prof.get("contacts", []) if not c.get("is_public")]
            if not initiator_private:
                raise HTTPException(status_code=400, detail="The other user no longer has private contacts to exchange.")
                
            await Database.db.contact_requests.update_one(
                {"req_id": payload.req_id}, 
                {"$set": {"status": "counter_pending", "counter_shared_contacts": shared_values}}
            )
            
            b_profile = await Database.get_active_profile(user_id)
            offered_contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in shared_values)
            prefix = (
                f"🔄 <b>MUTUAL EXCHANGE REQUEST!</b>\n"
                f"The user wants to exchange private contacts with you!\n"
                f"If you agree, you will receive these contacts of theirs:\n\n"
                f"{offered_contacts_text}\n\n"
                f"Please choose your option below:"
            )
            await send_profile(req['initiator_id'], b_profile, mutual_exchange_kb(payload.req_id), custom_prefix=prefix)
            return {"status": "ok"}
            
        elif payload.action == "agree_exchange":
            if req['initiator_id'] != user_id or req['status'] != 'counter_pending':
                raise HTTPException(status_code=403, detail="Permission denied.")
                
            await Database.db.contact_requests.update_one(
                {"req_id": payload.req_id}, 
                {"$set": {"status": "accepted", "initiator_shared_contacts": shared_values}}
            )
            
            b_contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in req['counter_shared_contacts'])
            a_contacts_text = "\n".join(f"• <code>{html.escape(v)}</code>" for v in shared_values)
            
            b_profile = await Database.get_active_profile(req['target_id'])
            await send_profile(user_id, b_profile, kb=None, custom_prefix="👤 <b>Exchanged Profile:</b>\n\n")
            await bot.send_message(
                user_id, 
                f"🤝 <b>Mutual Exchange Complete!</b>\nHere are the contact details they shared with you:\n\n{b_contacts_text}"
            )
            
            a_profile = await Database.get_active_profile(user_id)
            await send_profile(req['target_id'], a_profile, kb=None, custom_prefix="👤 <b>Exchanged Profile:</b>\n\n")
            await bot.send_message(
                req['target_id'], 
                f"🤝 <b>Mutual Exchange Complete!</b>\nHere are the contact details they shared with you:\n\n{a_contacts_text}"
            )
            return {"status": "ok"}
            
    raise HTTPException(status_code=400, detail="Invalid action")