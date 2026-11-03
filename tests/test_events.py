import asyncio
import pytest
from ghost_flow.core.events import EventManager, FlowEvent


def test_event_manager_pub_sub():
    async def _test():
        mgr = EventManager()
        received = []

        def on_custom_event(ev: FlowEvent):
            received.append(ev.data.get("val"))

        mgr.subscribe("custom", on_custom_event)

        await mgr.emit("custom", pipeline_name="p1", val="hello")
        await mgr.emit("custom", pipeline_name="p1", val="world")
        await mgr.emit("other", pipeline_name="p1", val="ignored")

        assert received == ["hello", "world"]
        assert len(mgr.history) == 3
    asyncio.run(_test())


def test_event_manager_global_subscriber():
    async def _test():
        mgr = EventManager()
        types = []

        def on_any(ev: FlowEvent):
            types.append(ev.event_type)

        mgr.subscribe_all(on_any)

        await mgr.emit("ev1", pipeline_name="p")
        await mgr.emit("ev2", pipeline_name="p")

        assert types == ["ev1", "ev2"]
    asyncio.run(_test())
