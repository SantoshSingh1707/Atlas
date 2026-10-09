from app.schemas import CapabilityResult, Citation, RunEvent, RunStatus, SearchResult
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
