import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas import WebhookResponse
from app.services.stripe_handler import process_stripe_event, verify_and_parse_event

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    payload = await request.body()

    try:
        event = verify_and_parse_event(payload, stripe_signature, settings.stripe_webhook_secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    record, is_duplicate = process_stripe_event(db, event)

    return WebhookResponse(
        received=True,
        event_id=record.event_id,
        event_type=record.event_type,
        duplicate=is_duplicate,
    )
