from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.schemas import CapabilityResult, Citation, RunEvent
from app.store.models import (
    CitationRow,
    Run,
    RunBundle,
    RunData,
    RunStep,
    StepData,
    _now,
)

_MEMORY_URLS = {"sqlite://", "sqlite:///:memory:"}


class RunStore:
    def __init__(self, database_url: str) -> None:
        if database_url in _MEMORY_URLS:
            # One shared connection so in-memory data survives across sessions.
            self._engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            self._engine = create_engine(database_url)
        SQLModel.metadata.create_all(self._engine)

    def create_run(self, capability_id: str, question: str) -> str:
        run_id = uuid4().hex
        run = Run(id=run_id, capability_id=capability_id, question=question, status="pending")
        with Session(self._engine) as session:
            session.add(run)
            session.commit()
        return run_id

    def add_step(self, event: RunEvent) -> None:
        with Session(self._engine) as session:
            session.add(
                RunStep(
                    run_id=event.run_id,
                    step=event.step,
                    status=event.status,
                    detail=event.detail,
                )
            )
            session.commit()

    def finalize(self, result: CapabilityResult) -> None:
        with Session(self._engine) as session:
            run = session.get(Run, result.run_id)
            if run is None:
                return
            run.status = result.status.value
            run.report_markdown = result.report_markdown
            run.error = result.error
            run.tokens = result.tokens
            run.cost = result.cost
            run.duration_ms = result.duration_ms
            run.updated_at = _now()
            for citation in result.citations:
                session.add(
                    CitationRow(
                        run_id=result.run_id,
                        index=citation.index,
                        title=citation.title,
                        url=citation.url,
                        snippet=citation.snippet,
                    )
                )
            session.commit()

    def fail(self, run_id: str, error: str) -> None:
        with Session(self._engine) as session:
            run = session.get(Run, run_id)
            if run is None:
                return
            run.status = "failed"
            run.error = error
            run.updated_at = _now()
            session.commit()

    def get_run(self, run_id: str) -> RunBundle | None:
        with Session(self._engine) as session:
            run = session.get(Run, run_id)
            if run is None:
                return None
            steps = session.exec(
                select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.id)
            ).all()
            rows = session.exec(
                select(CitationRow).where(CitationRow.run_id == run_id).order_by(CitationRow.index)
            ).all()
            return RunBundle(
                run=RunData.model_validate(run, from_attributes=True),
                steps=[StepData.model_validate(step, from_attributes=True) for step in steps],
                citations=[
                    Citation(index=row.index, title=row.title, url=row.url, snippet=row.snippet)
                    for row in rows
                ],
            )

    def list_runs(self, limit: int = 20, offset: int = 0) -> list[RunData]:
        with Session(self._engine) as session:
            runs = session.exec(
                select(Run)
                # rowid is monotonic per insert, so identical timestamps still
                # order newest-first deterministically (uuid ids would not).
                .order_by(Run.created_at.desc(), text("rowid DESC"))
                .offset(offset)
                .limit(limit)
            ).all()
            return [RunData.model_validate(run, from_attributes=True) for run in runs]
