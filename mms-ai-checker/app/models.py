from datetime import date
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Fact(StrictModel):
    field: Literal["legal_name", "registration_number", "expires_on"]
    value: str = Field(min_length=1, max_length=250)
    page: int = Field(ge=1, le=20)
    quote: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class Extraction(StrictModel):
    facts: list[Fact] = Field(max_length=3)


class CheckInput(StrictModel):
    question: str = Field(
        default="Hồ sơ này còn thiếu gì để được duyệt?", min_length=1, max_length=500
    )


class LabExperiment(StrictModel):
    """One Chunking Lab run; bounds keep a single request cheap."""

    max_words: int = Field(default=60, ge=10, le=200)
    overlap: int = Field(default=15, ge=0, le=150)
    candidate_k: int = Field(default=8, ge=1, le=20)
    rrf_k: int = Field(default=60, ge=1, le=200)
    coverage_weight: float = Field(default=0.02, ge=0, le=1)
    embedder: Literal["local", "fastembed", "gemini"] = "local"
    split: Literal["dev", "holdout", "all"] = "all"
    note: str = Field(default="", max_length=300)


class Feedback(StrictModel):
    finding_id: str = Field(pattern=r"^F[1-9][0-9]*$", max_length=30)
    verdict: Literal["correct", "incorrect", "needs_review"]
    note: str = Field(default="", max_length=1000)


class Finding(StrictModel):
    id: str
    rule: str
    code: str
    severity: Literal["blocker", "review"]
    message: str
    document_id: str | None = None
    page: int | None = None
    field: str | None = None
    quote: str | None = None
    source: Literal["document", "manifest"]


class Note(StrictModel):
    finding_id: str
    text: str = Field(min_length=1, max_length=500)


class Explanation(StrictModel):
    notes: list[Note] = Field(max_length=50)


class InvestigationInput(StrictModel):
    transaction_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{2,39}$")
    # Recorded for audit only. The workflow is fixed; the question cannot change which
    # data is read, the diagnosis or the steps.
    question: str = Field(
        default="Vì sao merchant chưa nhận được tiền? Tôi nên làm gì?", min_length=1, max_length=500
    )


class InvestigationNote(StrictModel):
    code: str = Field(pattern=r"^[a-z_]{2,40}$")
    text: str = Field(min_length=1, max_length=500)


class InvestigationExplanation(StrictModel):
    summary: str = Field(min_length=1, max_length=600)
    notes: list[InvestigationNote] = Field(max_length=20)


def parse_date(value: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Expected YYYY-MM-DD")
    return date.fromisoformat(value)
