from datetime import UTC, datetime

from sqlmodel import Session

from app.schemas import CapabilityResult, Citation, RunEvent, RunStatus, SearchResult
from app.store.models import Run
from app.store.repository import RunStore


def test_create_and_get():
    s = RunStore("sqlite://")
    rid = s.create_run("research", "what is rag")
    b = s.get_run(rid)
    assert b.run.question == "what is rag"
    assert b.run.status == "pending"


def test_add_step_and_finalize():
    s = RunStore("sqlite://")
    rid = s.create_run("research", "q")
    s.add_step(RunEvent(run_id=rid, step="plan", status="started"))
    s.finalize(CapabilityResult(
        run_id=rid, capability_id="research", status=RunStatus.finished, report_markdown="# R",
        citations=[Citation(index=1, title="t", url="https://x")],
        sources=[SearchResult(title="t", url="https://x")], tokens=10, cost=0.01, duration_ms=5))
    b = s.get_run(rid)
    assert b.run.status == "finished" and len(b.steps) == 1 and b.citations[0].index == 1


def test_list_runs_newest_first():
    s = RunStore("sqlite://")
    a = s.create_run("research", "a"); b = s.create_run("research", "b")
    assert [r.id for r in s.list_runs()] == [b, a]


def test_fail_sets_error():
    s = RunStore("sqlite://")
    rid = s.create_run("research", "q")
    s.fail(rid, "boom")
    assert s.get_run(rid).run.error == "boom"


def test_list_runs_ties_break_by_insertion_order():
    s = RunStore("sqlite://")
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    with Session(s._engine) as session:
        # Same created_at, and id order (zzz > aaa) is the reverse of insert order.
        session.add(
            Run(id="zzz", capability_id="research", question="first", created_at=ts, updated_at=ts)
        )
        session.add(
            Run(id="aaa", capability_id="research", question="second", created_at=ts, updated_at=ts)
        )
        session.commit()
    assert [r.id for r in s.list_runs()] == ["aaa", "zzz"]
