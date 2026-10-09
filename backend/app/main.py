from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import build_router
from app.config.settings import get_settings
from app.core.engine import RunEngine
from app.core.events import EventBus
from app.core.registry import CapabilityRegistry
from app.store.repository import RunStore


def create_app(registry: CapabilityRegistry | None = None, run_inline: bool = False) -> FastAPI:
    # Re-read the environment on every factory call so tests (and restarts) that
    # monkeypatch env vars are honored despite get_settings' lru_cache.
    get_settings.cache_clear()
    settings = get_settings()

    Path("data").mkdir(exist_ok=True)

    store = RunStore(settings.database_url)
    bus = EventBus()
    capabilities = registry if registry is not None else CapabilityRegistry()
    engine = RunEngine(store=store, bus=bus, capabilities=capabilities)

    app = FastAPI(title="Atlas")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(
        build_router(engine=engine, store=store, settings=settings, run_inline=run_inline)
    )

    app.state.engine = engine
    app.state.store = store
    app.state.registry = capabilities
    app.state.settings = settings
    return app


app = create_app()
