from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_orchestrator_without_langgraph(monkeypatch):
    module_name = "backend.app.ai.orchestrator_no_langgraph_test"
    for key in ("langgraph", "langgraph.graph", "langgraph.graph.message", module_name):
        monkeypatch.delitem(sys.modules, key, raising=False)
    # Make `from langgraph.graph import ...` fail with ModuleNotFoundError.
    monkeypatch.setitem(sys.modules, "langgraph", ModuleType("langgraph"))

    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "ai" / "orchestrator.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def test_fallback_stategraph_respects_nonconditional_edges(monkeypatch):
    orchestrator = _load_orchestrator_without_langgraph(monkeypatch)
    assert orchestrator.END == "__END__"

    graph = orchestrator.StateGraph(dict)
    order = []

    def agent(state):
        order.append("agent")
        turn = int(state.get("turn") or 0)
        if turn == 0:
            return {"turn": 1, "pending_tool": {"tool": "noop"}}
        return {"response": "ok", "halt": True, "pending_tool": None}

    def tool(state):
        order.append("tool")
        assert state.get("pending_tool") == {"tool": "noop"}
        return {"pending_tool": None}

    def route(state):
        if state.get("halt"):
            return orchestrator.END
        if state.get("pending_tool"):
            return "tool"
        return orchestrator.END

    graph.add_node("agent", agent)
    graph.add_node("tool", tool)
    graph.add_conditional_edges("agent", route, {"tool": "tool", orchestrator.END: orchestrator.END})
    graph.add_edge("tool", "agent")
    graph.set_entry_point("agent")

    result = graph.compile().invoke({"turn": 0, "halt": False, "pending_tool": None}, {"recursion_limit": 6})

    assert order == ["agent", "tool", "agent"]
    assert result.get("response") == "ok"
