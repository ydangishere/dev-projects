from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StripeEvent
from app.schemas import StripeEventOut

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events", response_model=list[StripeEventOut])
def list_events(db: Session = Depends(get_db)):
    return db.query(StripeEvent).order_by(StripeEvent.created_at.desc()).all()
