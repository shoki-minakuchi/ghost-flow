import pytest
from ghost_flow.core.context import FlowContext


def test_context_storage_and_retrieval():
    ctx = FlowContext({"env": "test"})
    assert ctx["env"] == "test"
    assert ctx.get("missing", "default") == "default"

    ctx.set("counter", 42)
    assert ctx["counter"] == 42


def test_context_results_and_artifacts():
    ctx = FlowContext()
    ctx.store_result("task1", "result_data", execution_time_sec=0.015)
    assert ctx.get_result("task1") == "result_data"
    assert ctx.timings["task1"] == 0.015

    ctx.store_artifact("config", {"timeout": 30})
    assert ctx.get_artifact("config")["timeout"] == 30

    d = ctx.to_dict()
    assert "results" in d
    assert "artifacts" in d
    assert "timings" in d
