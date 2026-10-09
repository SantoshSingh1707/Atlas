from app.core.engine import RunEngine
from app.core.events import EventBus
from app.core.registry import CapabilityRegistry
from app.schemas import CapabilityResult, RunEvent, RunStatus
from app.store.repository import RunStore


class DummyCapability:
    id = "dummy"

    def run(self, run_id, params, emit):
        emit(RunEvent(run_id=run_id, step="write", status="progress", detail="working"))
        return CapabilityResult(
            run_id=run_id,
            capability_id="dummy",
            status=RunStatus.finished,
            report_markdown=params["question"],
        )


def _engine():
    caps = CapabilityRegistry()
    caps.register("dummy", DummyCapability)
    return RunEngine(store=RunStore("sqlite://"), bus=EventBus(), capabilities=caps)


def test_execute_runs_capability_and_finalizes():
    e = _engine()
    rid = e.submit("dummy", {"question": "hello"})
    result = e.execute(rid)
    assert result.status == RunStatus.finished
    assert result.report_markdown == "hello"
    assert e.store.get_run(rid).run.status == "finished"
    assert [s.step for s in e.store.get_run(rid).steps] == ["write"]


def test_stream_yields_published_events_then_closes():
    e = _engine()
    rid = e.submit("dummy", {"question": "hi"})
    e.execute(rid)
    events = list(e.bus.stream(rid))
    assert events and events[-1].step in {"done", "error"}


def test_unknown_capability_raises():
    e = _engine()
    try:
        e.submit("nope", {})
        assert False, "expected KeyError"
    except KeyError:
        pass
