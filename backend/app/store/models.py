from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlmodel import Field, SQLModel

from app.schemas import Citation


def _now() -> datetime:
    """UTC timestamp. SQLModel's UTCDateTime column requires tz-aware values."""
    return datetime.now(UTC)


class Run(SQLModel, table=True):
    id: str = Field(primary_key=True)
    capability_id: str
    question: str = ""
    status: str = "pending"
    report_markdown: str | None = None
    error: str | None = None
    tokens: int = 0
    cost: float = 0.0
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class RunStep(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    step: str
    status: str
    detail: str | None = None
    created_at: datetime = Field(default_factory=_now)


class CitationRow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    index: int
    title: str
    url: str
    snippet: str = ""


class RunData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    capability_id: str
    question: str
    status: str
    report_markdown: str | None = None
    error: str | None = None
    tokens: int = 0
    cost: float = 0.0
    duration_ms: int = 0
    created_at: datetime
    updated_at: datetime


class StepData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    step: str
    status: str
    detail: str | None = None
    created_at: datetime


class RunBundle(BaseModel):
    run: RunData
    steps: list[StepData]
    citations: list[Citation]
