import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from ghost_flow.bridge.cockpit_bridge import CockpitBridge
from ghost_flow.core.events import EventManager, FlowEvent


def test_bridge_standalone_fallback():
    async def _test():
        # Connect to invalid port
        bridge = CockpitBridge(cockpit_url="ws://127.0.0.1:59999/ws")
        connected = await bridge.connect()
        assert connected is False
        assert bridge.is_connected is False

        # Should not throw when disconnected
        await bridge.set_master_directive("Directive")
        await bridge.register_agent("a1", "Agent", "Worker")
        await bridge.update_agent("a1", status="DONE")
        await bridge.disconnect()
    asyncio.run(_test())


def test_bridge_mocked_websocket():
    async def _test():
        ev_mgr = EventManager()
        bridge = CockpitBridge(cockpit_url="ws://mock/ws", event_manager=ev_mgr)

        mock_ws = AsyncMock()
        bridge.ws = mock_ws
        bridge.is_connected = True

        await bridge.set_master_directive("Test Directive")
        mock_ws.send_json.assert_called_with({
            "action": "set_llm_directive",
            "directive": "Test Directive",
        })

        await bridge.register_agent("ghost-test", "Ghost-Test", "Tester", color="#FF00FF")
        mock_ws.send_json.assert_called_with({
            "action": "register_agent",
            "agent_id": "ghost-test",
            "name": "Ghost-Test",
            "role": "Tester",
            "instruction": "Ready",
            "color": "#FF00FF",
            "status": "READY",
        })

        # Test event mapping
        await ev_mgr.emit(
            "task_running",
            pipeline_name="p",
            node_id="test_node",
            agent_role="Architect",
            description="Analyzing topology",
        )
        # Check that update_agent_status was sent
        calls = mock_ws.send_json.call_args_list
        assert any(c[0][0].get("action") == "update_agent_status" for c in calls)
    asyncio.run(_test())
