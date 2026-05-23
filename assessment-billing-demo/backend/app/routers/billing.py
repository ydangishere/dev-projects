from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BillingAccount
from app.schemas import BillingRead

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/status", response_model=BillingRead)
def billing_status(db: Session = Depends(get_db)):
    billing = db.query(BillingAccount).first()
    if billing is None:
        billing = BillingAccount()
        db.add(billing)
        db.commit()
        db.refresh(billing)

    return BillingRead(
        plan=billing.plan,
        status=billing.status,
        assessments_used=billing.assessments_used,
        assessments_limit=billing.assessments_limit,
        remaining=max(billing.assessments_limit - billing.assessments_used, 0),
        updated_at=billing.updated_at,
    )
