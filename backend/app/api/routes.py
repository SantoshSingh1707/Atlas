from __future__ import annotations

import json
import threading
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config.settings import Settings
from app.core.engine import RunEngine
from app.schemas import RunEvent
from app.store.repository import RunStore

_TERMINAL_STATUSES = {"finished", "failed"}


class RunRequest(BaseModel):
    capability: str
    question: str = Field(min_length=3, max_length=2000)
    options: dict | None = None


def _result_for(store: RunStore, run_id: str) -> dict | None:
    bundle = store.get_run(run_id)
    if bundle is None:
        return None
    run = bundle.run
    return {
        "run_id": run.id,
        "capability_id": run.capability_id,
        "status": run.status,
        "report_markdown": run.report_markdown or "",
        "citations": [citation.model_dump() for citation in bundle.citations],
        "sources": [],
        "tokens": run.tokens,
        "cost": run.cost,
        "duration_ms": run.duration_ms,
        "error": run.error,
    }


def build_router(
    *,
    engine: RunEngine,
    store: RunStore,
    settings: Settings,
    run_inline: bool,
) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    def healthz() -> dict:
        return {
            "status": "ok",
            "llm_provider": settings.llm_provider,
            "search_providers": settings.search_providers,
            "capabilities": engine.capabilities.ids(),
        }

    @router.post("/api/runs", status_code=202)
    def create_run(body: RunRequest) -> dict:
        try:
            run_id = engine.submit(
                body.capability,
                {"question": body.question, "options": body.options},
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"unknown capability: {body.capability}"
            ) from exc

        if run_inline:
            engine.execute(run_id)
        else:
            threading.Thread(target=engine.execute, args=(run_id,), daemon=True).start()
        return {"run_id": run_id}

    @router.get("/api/runs")
    def list_runs() -> list[dict]:
        return [run.model_dump(mode="json") for run in store.list_runs()]

    @router.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        result = _result_for(store, run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="run not found")
        return result

    @router.get("/api/runs/{run_id}/stream")
    def stream_run(run_id: str) -> StreamingResponse:
        if store.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="run not found")

        def generate() -> Iterator[str]:
            bundle = store.get_run(run_id)
            if bundle is not None and bundle.run.status in _TERMINAL_STATUSES:
                # Completed run: replay persisted steps so reconnects (and late
                # subscribers) terminate instead of blocking on an empty queue.
                for step in bundle.steps:
                    event = RunEvent(
                        run_id=run_id,
                        step=step.step,
                        status=step.status,
                        detail=step.detail,
                    )
                    yield f"event: {event.step}\ndata: {event.model_dump_json()}\n\n"
                engine.bus.close(run_id)
            else:
                for event in engine.bus.stream(run_id):
                    yield f"event: {event.step}\ndata: {event.model_dump_json()}\n\n"
            result = _result_for(store, run_id)
            if result is not None:
                yield f"event: result\ndata: {json.dumps(result)}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    return router
