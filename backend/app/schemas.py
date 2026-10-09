from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    finished = "finished"
    failed = "failed"


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    provider: str = ""


class ResearchOptions(BaseModel):
    max_sub_queries: int = 5
    results_per_query: int = 5
    max_sources_to_read: int = 8


class ResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    options: ResearchOptions | None = None


class RunEvent(BaseModel):
    run_id: str
    step: Literal["plan", "search", "read", "write", "done", "error"]
    status: Literal["started", "progress", "finished", "failed"]
    detail: str | None = None
    token: str | None = None


class Citation(BaseModel):
    index: int
    title: str
    url: str
    snippet: str = ""


class ResearchPlan(BaseModel):
    sub_queries: list[str]
    outline: str = ""


class Note(BaseModel):
    fact: str
    source_url: str
    source_title: str = ""


class ResearchNotes(BaseModel):
    notes: list[Note]


class CapabilityResult(BaseModel):
    run_id: str
    capability_id: str
    status: RunStatus
    report_markdown: str = ""
    citations: list[Citation] = []
    sources: list[SearchResult] = []
    tokens: int = 0
    cost: float = 0.0
    duration_ms: int = 0
    error: str | None = None


# v1 alias — the research capability returns a CapabilityResult
ResearchResult = CapabilityResult

