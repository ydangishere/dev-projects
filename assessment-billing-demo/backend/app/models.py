from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_name: Mapped[str] = mapped_column(String(120), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BillingAccount(Base):
    __tablename__ = "billing_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan: Mapped[str] = mapped_column(String(60), default="starter", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    assessments_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assessments_limit: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
