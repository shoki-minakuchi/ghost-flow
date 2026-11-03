import asyncio
import pytest
from ghost_flow.core.context import FlowContext
from ghost_flow.core.node import TaskNode, NodeStatus


def test_node_sync_execution():
    async def _test():
        ctx = FlowContext()
        node = TaskNode("sync_node", lambda c: "sync_ok")
        res = await node.execute(ctx)
        assert res == "sync_ok"
        assert node.status == NodeStatus.COMPLETED
        assert ctx.get_result("sync_node") == "sync_ok"
    asyncio.run(_test())


def test_node_async_execution():
    async def _test():
        ctx = FlowContext()

        async def async_handler(c):
            await asyncio.sleep(0.01)
            return "async_ok"

        node = TaskNode("async_node", async_handler)
        res = await node.execute(ctx)
        assert res == "async_ok"
        assert node.status == NodeStatus.COMPLETED
    asyncio.run(_test())


def test_node_retry_success():
    async def _test():
        ctx = FlowContext()
        attempt = 0

        def flaky_handler(c):
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                raise ValueError("Temporary glitch")
            return "recovered"

        node = TaskNode("retry_node", flaky_handler, retries=2)
        res = await node.execute(ctx)
        assert res == "recovered"
        assert node.attempts == 2
        assert node.status == NodeStatus.COMPLETED
    asyncio.run(_test())


def test_node_retry_exhausted():
    async def _test():
        ctx = FlowContext()

        def always_fail(c):
            raise RuntimeError("Fatal bug")

        node = TaskNode("fail_node", always_fail, retries=1)
        with pytest.raises(RuntimeError):
            await node.execute(ctx)
        assert node.status == NodeStatus.FAILED
        assert node.attempts == 2
    asyncio.run(_test())


def test_node_timeout():
    async def _test():
        ctx = FlowContext()

        async def slow_handler(c):
            await asyncio.sleep(0.5)
            return "too_late"

        node = TaskNode("timeout_node", slow_handler, timeout_sec=0.05)
        with pytest.raises(asyncio.TimeoutError):
            await node.execute(ctx)
        assert node.status == NodeStatus.FAILED
    asyncio.run(_test())
