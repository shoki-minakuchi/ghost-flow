import asyncio
import pytest
from ghost_flow.core.context import FlowContext
from ghost_flow.core.node import TaskNode, NodeStatus
from ghost_flow.core.pipeline import FlowPipeline


def test_sequential_pipeline():
    async def _test():
        pipeline = FlowPipeline("seq-pipeline")
        n1 = TaskNode("step1", lambda c: 10)
        n2 = TaskNode("step2", lambda c: c.get_result("step1") * 2, depends_on=["step1"])

        pipeline.add_nodes([n1, n2])
        results = await pipeline.run()

        assert results["step1"] == 10
        assert results["step2"] == 20
    asyncio.run(_test())


def test_diamond_dag_concurrency():
    async def _test():
        pipeline = FlowPipeline("diamond-pipeline")
        execution_order = []

        async def h_a(c):
            execution_order.append("A")
            return "A"

        async def h_b(c):
            await asyncio.sleep(0.02)
            execution_order.append("B")
            return "B"

        async def h_c(c):
            await asyncio.sleep(0.01)
            execution_order.append("C")
            return "C"

        async def h_d(c):
            execution_order.append("D")
            return f"{c.get_result('b')}+{c.get_result('c')}"

        node_a = TaskNode("a", h_a)
        node_b = TaskNode("b", h_b, depends_on=["a"])
        node_c = TaskNode("c", h_c, depends_on=["a"])
        node_d = TaskNode("d", h_d, depends_on=["b", "c"])

        pipeline.add_nodes([node_a, node_b, node_c, node_d])
        results = await pipeline.run()

        assert results["d"] == "B+C"
        assert execution_order[0] == "A"
        assert execution_order[-1] == "D"
        assert set(execution_order[1:3]) == {"B", "C"}
    asyncio.run(_test())


def test_cycle_detection():
    async def _test():
        pipeline = FlowPipeline("cycle-pipeline")
        n1 = TaskNode("node1", lambda c: None, depends_on=["node2"])
        n2 = TaskNode("node2", lambda c: None, depends_on=["node1"])

        pipeline.add_nodes([n1, n2])
        with pytest.raises(ValueError, match="contains a circular dependency"):
            await pipeline.run()
    asyncio.run(_test())


def test_missing_dependency():
    async def _test():
        pipeline = FlowPipeline("missing-dep")
        n1 = TaskNode("node1", lambda c: None, depends_on=["non_existent"])

        pipeline.add_node(n1)
        with pytest.raises(ValueError, match="depends on non-existent node"):
            await pipeline.run()
    asyncio.run(_test())


def test_downstream_skipped_on_failure_no_fail_fast():
    async def _test():
        pipeline = FlowPipeline("skip-pipeline", fail_fast=False)

        def failing_task(c):
            raise ValueError("Intentional crash")

        n1 = TaskNode("fail", failing_task)
        n2 = TaskNode("dependent", lambda c: "unreachable", depends_on=["fail"])

        pipeline.add_nodes([n1, n2])
        results = await pipeline.run()

        assert "dependent" not in results
        assert n2.status == NodeStatus.SKIPPED
        assert n1.status == NodeStatus.FAILED
    asyncio.run(_test())
