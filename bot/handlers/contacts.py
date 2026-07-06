import uuid
import html
import logging
import re
import urllib.parse
import aiohttp
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from bot.states import ProfileSetup
from bot.keyboards import edit_info_menu_kb, cancel_fsm_kb, manage_contacts_inline_kb
from infrastructure.locales import _, _btn
from application.services import ProfileService

router = Router()
logger = logging.getLogger(__name__)

async def verify_contact(val: str, lang: str) -> tuple[bool, str]:
    val = val.strip()
    if re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', val): return True, val
    if re.match(r'^\+?[0-9\s\-\(\)]{7,20}$', val) and any(c.isdigit() for c in val):
        try:
            import phonenumbers
            parsed = phonenumbers.parse(val if val.startswith('+') else '+' + val, None)
            if phonenumbers.is_valid_number(parsed): 
                return True, phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            else: 
                return False, _("con_add_instr", lang)
        except Exception: 
            pass
            
    url_pattern = re.compile(r'^(https?://)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(/[^\s]*)?$')
    if url_pattern.match(val):
        test_url = val if val.startswith('http') else 'https://' + val
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, timeout=5, allow_redirects=True) as resp:
                    if resp.status != 404: return True, test_url
                    else: return False, "❌ 404 URL."
        except Exception: return False, "❌ URL Error."
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(val)}&format=json&limit=1"
            async with session.get(url, headers={"User-Agent": "DayDatingBot/1.0"}, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0: return True, data[0].get("display_name", val)
    except Exception: pass
    return False, _("con_add_instr", lang)

@router.message(F.text.in_(_btn("btn_contacts")))
async def manage_contacts_menu(message: types.Message, lang: str, profile_service: ProfileService):
    active_prof = await profile_service.get_active_profile(message.from_user.id)
    if not active_prof: return await message.answer(_("prof_not_found", lang))
    
    await profile_service.sync_telegram_username(active_prof, message.from_user.username)
    active_prof = await profile_service.get_active_profile(message.from_user.id)
    
    contacts = active_prof.get("contacts", [])
    text = _("con_manage", lang)
    if contacts:
        for i, c in enumerate(contacts):
            visibility = _("con_pub", lang) if c.get("is_public") else _("con_priv", lang)
            text += f"{i+1}. <code>{html.escape(c['value'])}</code> ({visibility})\n"
    else:
        text += _("con_none", lang)
        
    kb = manage_contacts_inline_kb(lang, contacts)
    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data == "add_contact_fsm")
async def add_contact_fsm_start(callback: types.CallbackQuery, state: FSMContext, lang: str, profile_service: ProfileService):
    active_prof = await profile_service.get_active_profile(callback.from_user.id)
    if not active_prof: return await callback.answer(_("prof_not_found", lang), show_alert=True)
    
    await state.set_state(ProfileSetup.waiting_for_contact_val)
    await callback.message.answer(_("con_add_instr", lang), reply_markup=cancel_fsm_kb(lang))
    await callback.answer()

@router.message(ProfileSetup.waiting_for_contact_val, ~F.text.startswith("/"))
async def capture_new_contact(message: types.Message, state: FSMContext, lang: str, profile_service: ProfileService):
    if message.text and message.text in _btn("btn_cancel"):
        from bot.handlers.base import fsm_cancel
        await fsm_cancel(message, state, lang, profile_service)
        return
    if message.content_type != 'text': 
        return await message.answer(_("invalid_text", lang))
    
    user_id = message.from_user.id
    active_prof = await profile_service.get_active_profile(user_id)
    if not active_prof: return await message.answer(_("prof_not_found", lang))
    
    contacts = active_prof.get("contacts", [])
    if len(contacts) >= 8:
        await state.clear()
        await message.answer(_("con_max", lang), reply_markup=edit_info_menu_kb(lang))
        await manage_contacts_menu(message, lang, profile_service)
        return
        
    contact_val = message.text.strip()
    if len(contact_val) > 100: return await message.answer(_("con_err_len", lang))
    if "\n" in contact_val or "\r" in contact_val: return await message.answer(_("con_err_line", lang))
    if len(contact_val) < 3: return await message.answer(_("con_err_short", lang))
    
    wait_msg = await message.answer(_("con_verifying", lang))
    is_valid, result_val = await verify_contact(contact_val, lang)
    await wait_msg.delete()
    
    if not is_valid:
        return await message.answer(f"{result_val}\n\nPlease try again:")
        
    if len(result_val) > 100: result_val = result_val[:97] + "..."
    
    cid = uuid.uuid4().hex[:8]
    contacts.append({"id": cid, "type": "custom", "value": result_val, "is_public": False})
    
    await profile_service.update_profile(active_prof['public_uuid'], {"contacts": contacts})
    
    await message.answer(_("con_added", lang), reply_markup=edit_info_menu_kb(lang))
    await state.clear()
    await manage_contacts_menu(message, lang, profile_service)

@router.callback_query(F.data.startswith("togglecon_"))
async def toggle_contact_visibility(callback: types.CallbackQuery, lang: str, profile_service: ProfileService):
    cid = callback.data.replace("togglecon_", "", 1)
    active_prof = await profile_service.get_active_profile(callback.from_user.id)
    if not active_prof: return await callback.answer(_("prof_not_found", lang), show_alert=True)
    
    contacts = active_prof.get("contacts", [])
    updated = False
    for c in contacts:
        if c.get("id") == cid:
            c["is_public"] = not c.get("is_public", False)
            updated = True
            break
            
    if updated:
        await profile_service.update_profile(active_prof['public_uuid'], {"contacts": contacts})
        await callback.answer(_("con_toggled", lang))
        
        active_prof = await profile_service.get_profile_by_uuid(active_prof["public_uuid"])
        contacts = active_prof.get("contacts", [])
        text = _("con_manage", lang)
        for i, c in enumerate(contacts):
            visibility = _("con_pub", lang) if c.get("is_public") else _("con_priv", lang)
            text += f"{i+1}. <code>{html.escape(c['value'])}</code> ({visibility})\n"
            
        await callback.message.edit_text(text, reply_markup=manage_contacts_inline_kb(lang, contacts))
    else:
        await callback.answer(_("con_not_found", lang), show_alert=True)

@router.callback_query(F.data.startswith("delcon_"))
async def delete_contact(callback: types.CallbackQuery, lang: str, profile_service: ProfileService):
    cid = callback.data.replace("delcon_", "", 1)
    if cid == "tg_username": return await callback.answer(_("con_no_del_tg", lang), show_alert=True)
        
    active_prof = await profile_service.get_active_profile(callback.from_user.id)
    if not active_prof: return await callback.answer(_("prof_not_found", lang), show_alert=True)
    
    contacts = [c for c in active_prof.get("contacts", []) if c.get("id") != cid]
    await profile_service.update_profile(active_prof['public_uuid'], {"contacts": contacts})
    await callback.answer(_("con_deleted", lang))
    
    active_prof = await profile_service.get_profile_by_uuid(active_prof["public_uuid"])
    text = _("con_manage", lang)
    if contacts:
        for i, c in enumerate(contacts):
            visibility = _("con_pub", lang) if c.get("is_public") else _("con_priv", lang)
            text += f"{i+1}. <code>{html.escape(c['value'])}</code> ({visibility})\n"
    else:
        text += _("con_none", lang)
        
    await callback.message.edit_text(text, reply_markup=manage_contacts_inline_kb(lang, contacts))