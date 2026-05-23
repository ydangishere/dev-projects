from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Assessment, BillingAccount
from app.schemas import AssessmentCreate, AssessmentRead

router = APIRouter(prefix="/assessments", tags=["assessments"])


def _get_or_create_billing(db: Session) -> BillingAccount:
    billing = db.query(BillingAccount).first()
    if billing is None:
        billing = BillingAccount()
        db.add(billing)
        db.commit()
        db.refresh(billing)
    return billing


@router.get("", response_model=list[AssessmentRead])
def list_assessments(db: Session = Depends(get_db)):
    return db.query(Assessment).order_by(Assessment.created_at.desc()).all()


@router.post("", response_model=AssessmentRead, status_code=status.HTTP_201_CREATED)
def create_assessment(payload: AssessmentCreate, db: Session = Depends(get_db)):
    billing = _get_or_create_billing(db)
    if billing.assessments_used >= billing.assessments_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Assessment limit reached. Upgrade billing plan to continue.",
        )

    assessment = Assessment(**payload.model_dump())
    db.add(assessment)
    billing.assessments_used += 1
    db.commit()
    db.refresh(assessment)
    return assessment


@router.get("/{assessment_id}", response_model=AssessmentRead)
def get_assessment(assessment_id: int, db: Session = Depends(get_db)):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    return assessment


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(assessment_id: int, db: Session = Depends(get_db)):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    db.delete(assessment)
    db.commit()
