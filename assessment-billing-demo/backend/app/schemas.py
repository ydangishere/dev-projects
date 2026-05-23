from datetime import datetime

from pydantic import BaseModel, Field


class AssessmentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    subject_name: str = Field(min_length=2, max_length=120)
    score: float = Field(ge=0, le=100)
    status: str = Field(default="draft", pattern="^(draft|submitted|reviewed)$")
    notes: str | None = None


class AssessmentRead(BaseModel):
    id: int
    title: str
    subject_name: str
    score: float
    status: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BillingRead(BaseModel):
    plan: str
    status: str
    assessments_used: int
    assessments_limit: int
    remaining: int
    updated_at: datetime

    model_config = {"from_attributes": True}
