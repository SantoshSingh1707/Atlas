from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from app.schemas import CapabilityResult, RunEvent


class Tool(Protocol):
    name: str
    description: str

    def run(self, **kwargs: Any) -> Any: ...


class Capability(Protocol):
    id: str

    def run(
        self,
        run_id: str,
        params: dict,
        emit: Callable[[RunEvent], None],
    ) -> CapabilityResult: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools)


class CapabilityRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], Capability]] = {}

    def register(self, capability_id: str, factory: Callable[[], Capability]) -> None:
        if capability_id in self._factories:
            raise ValueError(f"capability already registered: {capability_id}")
        self._factories[capability_id] = factory

    def create(self, capability_id: str) -> Capability:
        return self._factories[capability_id]()

    def ids(self) -> list[str]:
        return list(self._factories)
