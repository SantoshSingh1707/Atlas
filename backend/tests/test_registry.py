import pytest

from app.core.registry import CapabilityRegistry, ToolRegistry


class EchoTool:
    name = "echo"
    description = "returns input"

    def run(self, text):
        return text


def test_tool_registry_roundtrip():
    r = ToolRegistry()
    r.register(EchoTool())
    assert r.names() == ["echo"]
    assert r.get("echo").run(text="hi") == "hi"


def test_tool_registry_unknown_raises():
    with pytest.raises(KeyError):
        ToolRegistry().get("nope")


def test_capability_registry_roundtrip():
    r = CapabilityRegistry()
    r.register("dummy", lambda: object())
    assert r.ids() == ["dummy"]
    assert r.create("dummy") is not None


def test_capability_registry_unknown_raises():
    with pytest.raises(KeyError):
        CapabilityRegistry().create("nope")
