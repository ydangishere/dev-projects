"""Linh Contact Onboarding AI Agent: runnable offline FastAPI demonstration."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.linh import guide_onboarding

app = FastAPI(title="Linh Contact Onboarding AI Agent", version="1.0.0")

# Demo-only volatile memory. Replace with authorized, encrypted, scoped DB data.
SYNCED: dict[str, set[str]] = {}
INVITES: dict[str, "Invite"] = {}
_SECRET = os.getenv("CONTACT_HASH_KEY", "demo-only-do-not-use-in-production")
MAX_BATCH = 100


class Contact(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=7, max_length=25)


class SyncRequest(BaseModel):
    contacts: list[Contact] = Field(max_length=MAX_BATCH)
    permission: Literal["full", "limited", "denied", "not_requested"]
    sync_consent: bool = False


class InviteRequest(BaseModel):
    contact: Contact
    source: Literal["native_picker", "in_app_list"]
    user_selected: bool


class GuideRequest(BaseModel):
    flow: Literal["sync", "invite", "skip"]
    permission: Literal["full", "limited", "denied", "not_requested"] = "not_requested"
    selected_count: int = Field(default=0, ge=0, le=100)
    language: Literal["vi", "en"] = "vi"


@dataclass
class Invite:
    owner_id: str
    masked_phone: str
    first_name: str
    confirmed: bool = False
    status: str = "draft"


def actor(x_demo_user: str = Header(default="demo-user")) -> str:
    """Demo owner header is NOT authentication. Use validated JWT/session in production."""
    if not 1 <= len(x_demo_user) <= 80 or not re.fullmatch(r"[a-zA-Z0-9_-]+", x_demo_user):
        raise HTTPException(400, "Invalid demo user header")
    return x_demo_user


def normalize_phone(raw: str) -> str:
    """Vietnam-oriented E.164 demo normalization, not a global phone parser."""
    phone = re.sub(r"[\s().-]", "", raw)
    if phone.startswith("0"):
        phone = "+84" + phone[1:]
    elif phone.startswith("84"):
        phone = "+" + phone
    if not re.fullmatch(r"\+[1-9]\d{7,14}", phone):
        raise HTTPException(422, "Expected E.164 or VN mobile number")
    return phone


def digest_phone(phone: str) -> str:
    return hmac.new(_SECRET.encode(), phone.encode(), hashlib.sha256).hexdigest()


def mask_phone(phone: str) -> str:
    return "***" + phone[-4:]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "persona": "Linh (simulated AI)", "real_contacts_connected": False}


@app.post("/agent/linh/guide")
def agent_guide(payload: GuideRequest) -> dict:
    # Optional LLM sees operational metadata only, never the contact list or PII.
    return guide_onboarding(payload.model_dump())


@app.post("/contacts/sync")
def sync_contacts(payload: SyncRequest, x_demo_user: str = Header(default="demo-user")) -> dict:
    owner = actor(x_demo_user)
    if not payload.sync_consent:
        raise HTTPException(403, "Explicit contact sync consent required")
    if payload.permission not in ("full", "limited"):
        raise HTTPException(403, "OS contacts permission required for app-managed sync")
    # The permission field is only a demo signal, NOT proof of real OS authorization.
    numbers = {digest_phone(normalize_phone(c.phone)) for c in payload.contacts}
    SYNCED.setdefault(owner, set()).update(numbers)
    return {"synced": len(numbers), "total_unique": len(SYNCED[owner]), "stored": "HMAC digests only", "ai_used": False}


@app.get("/contacts/sync/summary")
def sync_summary(x_demo_user: str = Header(default="demo-user")) -> dict:
    owner = actor(x_demo_user)
    return {"total_unique": len(SYNCED.get(owner, set()))}


@app.delete("/contacts/sync")
def delete_sync(x_demo_user: str = Header(default="demo-user")) -> dict:
    owner = actor(x_demo_user)
    deleted = len(SYNCED.pop(owner, set()))
    return {"deleted": deleted, "owner": owner}


@app.post("/invitations/draft")
def draft_invite(payload: InviteRequest, x_demo_user: str = Header(default="demo-user")) -> dict:
    owner = actor(x_demo_user)
    if not payload.user_selected:
        raise HTTPException(403, "User must select the contact before an invitation draft")
    phone = normalize_phone(payload.contact.phone)
    invite_id = secrets.token_urlsafe(12)
    # Persist only masked phone and first name in volatile demo state.
    INVITES[invite_id] = Invite(owner_id=owner, masked_phone=mask_phone(phone), first_name=payload.contact.name.split()[0])
    return {"id": invite_id, "status": "draft", "source": payload.source,
            "message": f"Chào {INVITES[invite_id].first_name}, mình mời bạn tìm hiểu ứng dụng Referral nhé!",
            "requires_user_confirmation": True, "sent": False}


def owned_invite(invite_id: str, owner: str) -> Invite:
    invitation = INVITES.get(invite_id)
    if invitation is None or invitation.owner_id != owner:
        raise HTTPException(404, "Invitation not found")
    return invitation


@app.post("/invitations/{invite_id}/confirm")
def confirm_invite(invite_id: str, x_demo_user: str = Header(default="demo-user")) -> dict:
    invitation = owned_invite(invite_id, actor(x_demo_user))
    invitation.confirmed = True
    invitation.status = "ready_to_share"
    # Only mobile opens the native Share Sheet; this API never sends SMS/Zalo.
    return {"id": invite_id, "status": invitation.status, "sent": False,
            "share_url": f"https://example.invalid/referral/{invite_id}",
            "next_action": "Open native Share Sheet after user confirmation"}


@app.get("/invitations/{invite_id}")
def invitation_status(invite_id: str, x_demo_user: str = Header(default="demo-user")) -> dict:
    invitation = owned_invite(invite_id, actor(x_demo_user))
    return {"id": invite_id, "status": invitation.status, "masked_phone": invitation.masked_phone,
            "confirmed": invitation.confirmed, "sent": False,
            "registration_tracking": "not connected (demo)"}
