import uuid
import html
import logging
import re
import urllib.parse
import aiohttp
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from bot.states import ProfileSetup
from bot.keyboards import (
    edit_info_menu_kb,
    cancel_fsm_kb,
    manage_contacts_inline_kb
)
from core.database import Database
from core.locales import _, _btn

router = Router()
logger = logging.getLogger(__name__)

async def verify_contact(val: str, lang: str) -> tuple[bool, str]:
    val = val.strip()

    # 1. Email Check
    if re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', val):
        return True, val

    # 2. Phone Number Check
    if re.match(r'^\+?[0-9\s\-\(\)]{7,20}$', val) and any(c.isdigit() for c in val):
        try:
            import phonenumbers
            parsed = phonenumbers.parse(val if val.startswith('+') else '+' + val, None)
            if phonenumbers.is_valid_number(parsed):
                formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                return True, formatted
            else:
                return False, _("con_add_instr", lang)
        except ImportError:
            return True, val
        except Exception:
            return False, "❌ Format Error."

    # 3. Link / URL Check
    url_pattern = re.compile(r'^(https?://)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(/[^\s]*)?$')
    match = url_pattern.match(val)
    if match:
        test_url = val if val.startswith('http') else 'https://' + val
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, timeout=5, allow_redirects=True) as resp:
                    if resp.status != 404:
                        return True, test_url
                    else:
                        return False, "❌ 404 URL."
        except aiohttp.ClientError:
            return False, "❌ DNS Error."
        except Exception:
            return False, "❌ URL Exception."

    # 4. Address / Geographic Location Check
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "DayDatingBot/1.0 (Contact Verification)"}
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(val)}&format=json&limit=1"
            async with session.get(url, headers=headers, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0:
                        display_name = data[0].get("display_name", val)
                        return True, display_name
    except Exception as e:
        logger.error(f"Geocoding error: {e}")

    return False, _("con_add_instr", lang)

@router.message(F.text.in_(_btn("btn_contacts")))
async def manage_contacts_menu(message: types.Message, lang: str):
    active_prof = await Database.get_active_profile(message.from_user.id)
    await Database.sync_telegram_username(active_prof, message.from_user.username)
    active_prof = await Database.get_active_profile(message.from_user.id)
    
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
async def add_contact_fsm_start(callback: types.CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(ProfileSetup.waiting_for_contact_val)
    await callback.message.answer(_("con_add_instr", lang), reply_markup=cancel_fsm_kb(lang))
    await callback.answer()

@router.message(ProfileSetup.waiting_for_contact_val)
async def capture_new_contact(message: types.Message, state: FSMContext, lang: str):
    if message.text == _("btn_cancel", lang):
        from bot.handlers.base import fsm_cancel
        await fsm_cancel(message, state, lang)
        return
    if message.content_type != 'text': 
        return await message.answer(_("invalid_text", lang))
    
    user_id = message.from_user.id
    active_prof = await Database.get_active_profile(user_id)
    
    contacts = active_prof.get("contacts", [])
    if len(contacts) >= 8:
        await state.clear()
        await message.answer(_("con_max", lang), reply_markup=edit_info_menu_kb(lang))
        await manage_contacts_menu(message, lang)
        return
        
    contact_val = message.text.strip()
    
    if len(contact_val) > 100:
        return await message.answer(_("con_err_len", lang))
    if "\n" in contact_val or "\r" in contact_val:
        return await message.answer(_("con_err_line", lang))
    if len(contact_val) < 3:
        return await message.answer(_("con_err_short", lang))
    
    wait_msg = await message.answer(_("con_verifying", lang))
    is_valid, result_val = await verify_contact(contact_val, lang)
    await wait_msg.delete()
    
    if not is_valid:
        return await message.answer(f"{result_val}\n\nPlease try again:")
        
    if len(result_val) > 100:
        result_val = result_val[:97] + "..."
    
    cid = uuid.uuid4().hex[:8]
    new_contact = {
        "id": cid,
        "type": "custom",
        "value": result_val,
        "is_public": False 
    }
    
    await Database.db.profiles.update_one(
        {"public_uuid": active_prof['public_uuid']},
        {"$push": {"contacts": new_contact}}
    )
    
    await message.answer(_("con_added", lang), reply_markup=edit_info_menu_kb(lang))
    await state.clear()
    await manage_contacts_menu(message, lang)

@router.callback_query(F.data.startswith("togglecon_"))
async def toggle_contact_visibility(callback: types.CallbackQuery, lang: str):
    cid = callback.data.replace("togglecon_", "", 1)
    active_prof = await Database.get_active_profile(callback.from_user.id)
    
    contacts = active_prof.get("contacts", [])
    updated = False
    for c in contacts:
        if c.get("id") == cid:
            c["is_public"] = not c.get("is_public", False)
            updated = True
            break
            
    if updated:
        await Database.db.profiles.update_one({"_id": active_prof["_id"]}, {"$set": {"contacts": contacts}})
        await callback.answer(_("con_toggled", lang))
        
        active_prof = await Database.get_profile_by_uuid(active_prof["public_uuid"])
        contacts = active_prof.get("contacts", [])
        text = _("con_manage", lang)
        for i, c in enumerate(contacts):
            visibility = _("con_pub", lang) if c.get("is_public") else _("con_priv", lang)
            text += f"{i+1}. <code>{html.escape(c['value'])}</code> ({visibility})\n"
            
        await callback.message.edit_text(text, reply_markup=manage_contacts_inline_kb(lang, contacts))
    else:
        await callback.answer(_("con_not_found", lang), show_alert=True)

@router.callback_query(F.data.startswith("delcon_"))
async def delete_contact(callback: types.CallbackQuery, lang: str):
    cid = callback.data.replace("delcon_", "", 1)
    if cid == "tg_username":
        return await callback.answer(_("con_no_del_tg", lang), show_alert=True)
        
    active_prof = await Database.get_active_profile(callback.from_user.id)
    await Database.db.profiles.update_one(
        {"_id": active_prof["_id"]},
        {"$pull": {"contacts": {"id": cid}}}
    )
    await callback.answer(_("con_deleted", lang))
    
    active_prof = await Database.get_profile_by_uuid(active_prof["public_uuid"])
    contacts = active_prof.get("contacts", [])
    text = _("con_manage", lang)
    if contacts:
        for i, c in enumerate(contacts):
            visibility = _("con_pub", lang) if c.get("is_public") else _("con_priv", lang)
            text += f"{i+1}. <code>{html.escape(c['value'])}</code> ({visibility})\n"
    else:
        text += _("con_none", lang)
        
    await callback.message.edit_text(text, reply_markup=manage_contacts_inline_kb(lang, contacts))