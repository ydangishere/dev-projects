from datetime import datetime

from pydantic import BaseModel


class StripeEventOut(BaseModel):
    id: int
    event_id: str
    event_type: str
    status: str
    payload_summary: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookResponse(BaseModel):
    received: bool
    event_id: str
    event_type: str
    duplicate: bool = False
