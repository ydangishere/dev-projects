import json
from typing import Any

import stripe
from sqlalchemy.orm import Session

from app.models import StripeEvent


SUPPORTED_EVENTS = {
    "checkout.session.completed",
    "invoice.paid",
    "customer.subscription.updated",
}


def summarize_payload(event_type: str, data: dict[str, Any]) -> str:
    obj = data.get("object", {})
    if event_type == "checkout.session.completed":
        return json.dumps(
            {
                "session_id": obj.get("id"),
                "customer_email": obj.get("customer_details", {}).get("email"),
                "amount_total": obj.get("amount_total"),
                "currency": obj.get("currency"),
            }
        )
    if event_type == "invoice.paid":
        return json.dumps(
            {
                "invoice_id": obj.get("id"),
                "customer": obj.get("customer"),
                "amount_paid": obj.get("amount_paid"),
                "subscription": obj.get("subscription"),
            }
        )
    if event_type == "customer.subscription.updated":
        return json.dumps(
            {
                "subscription_id": obj.get("id"),
                "status": obj.get("status"),
                "customer": obj.get("customer"),
            }
        )
    return json.dumps({"object_id": obj.get("id")})


def process_stripe_event(db: Session, event: stripe.Event) -> tuple[StripeEvent, bool]:
    """Persist event with idempotency. Returns (record, is_duplicate)."""
    existing = db.query(StripeEvent).filter(StripeEvent.event_id == event.id).first()
    if existing:
        return existing, True

    event_type = event.type
    status = "processed" if event_type in SUPPORTED_EVENTS else "ignored"

    record = StripeEvent(
        event_id=event.id,
        event_type=event_type,
        status=status,
        payload_summary=summarize_payload(event_type, event.data),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, False


def verify_and_parse_event(payload: bytes, sig_header: str, webhook_secret: str) -> stripe.Event:
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
