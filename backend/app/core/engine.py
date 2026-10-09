from __future__ import annotations

from app.core.events import EventBus
from app.core.registry import CapabilityRegistry
from app.schemas import CapabilityResult, RunEvent, RunStatus
from app.store.repository import RunStore


class RunEngine:
    """Drives a registered capability and records its events and result."""

    def __init__(
        self,
        *,
        store: RunStore,
        bus: EventBus,
        capabilities: CapabilityRegistry,
    ) -> None:
        self.store = store
        self.bus = bus
        self.capabilities = capabilities
        self._params: dict[str, dict] = {}

    def submit(self, capability_id: str, params: dict) -> str:
        if capability_id not in self.capabilities.ids():
            raise KeyError(capability_id)
        run_id = self.store.create_run(capability_id, params.get("question", ""))
        self._params[run_id] = dict(params)
        return run_id

    def execute(self, run_id: str) -> CapabilityResult:
        bundle = self.store.get_run(run_id)
        if bundle is None:
            raise KeyError(run_id)
        capability_id = bundle.run.capability_id
        params = self._params.pop(run_id, {"question": bundle.run.question})
        capability = self.capabilities.create(capability_id)

        def emit(event: RunEvent) -> None:
            self.store.add_step(event)
            self.bus.publish(event)

        try:
            result = capability.run(run_id, params, emit)
        except Exception as exc:  # noqa: BLE001 — a capability failure must never crash the engine
            self.store.fail(run_id, str(exc))
            self.bus.publish(
                RunEvent(run_id=run_id, step="error", status="failed", detail=str(exc))
            )
            return CapabilityResult(
                run_id=run_id,
                capability_id=capability_id,
                status=RunStatus.failed,
                error=str(exc),
            )

        self.store.finalize(result)
        self.bus.publish(RunEvent(run_id=run_id, step="done", status="finished"))
        return result
