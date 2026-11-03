"""
CockpitBridge - Direct WebSocket bridge connecting GhostFlow to the GhostGym Swarm Cockpit.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import aiohttp
from ghost_flow.core.events import EventManager, FlowEvent

logger = logging.getLogger("ghost_flow.bridge")


class CockpitBridge:
    """Synchronizes GhostFlow pipeline states with GhostGym Live Web Cockpit."""

    def __init__(
        self,
        cockpit_url: str = "ws://127.0.0.1:8765/ws",
        event_manager: Optional[EventManager] = None,
    ):
        self.cockpit_url = cockpit_url
        self.event_manager = event_manager
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_connected = False
        self._registered_agents: Dict[str, Dict[str, Any]] = {}

        if self.event_manager:
            self.event_manager.subscribe_all(self._handle_pipeline_event)

    async def connect(self) -> bool:
        """Attempts to connect to the GhostGym WebSocket server."""
        try:
            self.session = aiohttp.ClientSession()
            timeout = aiohttp.ClientWSTimeout(ws_close=3.0) if hasattr(aiohttp, "ClientWSTimeout") else 3.0
            self.ws = await self.session.ws_connect(self.cockpit_url, timeout=timeout)
            self.is_connected = True
            logger.info("Connected to GhostGym Cockpit at %s", self.cockpit_url)
            return True
        except Exception as e:
            logger.warning("Cockpit offline or unreachable (%s). Running in standalone mode.", e)
            self.is_connected = False
            return False

    async def disconnect(self) -> None:
        """Closes the WebSocket connection."""
        try:
            if self.ws and not self.ws.closed:
                await self.ws.close()
            if self.session and not self.session.closed:
                await self.session.close()
        except Exception:
            pass
        finally:
            self.is_connected = False

    async def set_master_directive(self, directive: str) -> None:
        """Sets the Antigravity Master Commander directive in the cockpit."""
        if not self.is_connected or not self.ws:
            return
        await self.ws.send_json({
            "action": "set_llm_directive",
            "directive": directive,
        })

    async def register_agent(
        self,
        agent_id: str,
        name: str,
        role: str,
        instruction: str = "Ready",
        color: str = "#00F0FF",
        status: str = "READY",
    ) -> None:
        """Registers a dynamic sub-agent in the GhostGym topology map and cockpit."""
        self._registered_agents[agent_id] = {
            "name": name,
            "role": role,
            "instruction": instruction,
            "color": color,
            "status": status,
        }
        if not self.is_connected or not self.ws:
            return

        await self.ws.send_json({
            "action": "register_agent",
            "agent_id": agent_id,
            "name": name,
            "role": role,
            "instruction": instruction,
            "color": color,
            "status": status,
        })

    async def update_agent(
        self,
        agent_id: str,
        instruction: Optional[str] = None,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        latency: Optional[float] = None,
    ) -> None:
        """Updates agent instruction, progress percentage, latency, and status badge."""
        if not self.is_connected or not self.ws:
            return

        payload: Dict[str, Any] = {"action": "update_agent_status", "agent_id": agent_id}
        if instruction is not None:
            payload["instruction"] = instruction
        if status is not None:
            payload["status"] = status
        if progress is not None:
            payload["progress"] = progress
        if latency is not None:
            payload["latency"] = latency

        await self.ws.send_json(payload)

    async def _handle_pipeline_event(self, event: FlowEvent) -> None:
        """Automatically maps FlowEvents to Swarm Cockpit agent statuses."""
        if not self.is_connected:
            return

        node_id = event.node_id
        agent_role = event.data.get("agent_role") or "Flow-Worker"
        agent_id = f"flow-{agent_role.lower().replace(' ', '-')}"

        if event.event_type == "task_running":
            desc = event.data.get("description", f"Running {node_id}")
            await self.update_agent(
                agent_id=agent_id,
                instruction=f"⚙️ {desc}",
                status="ACTIVE",
                progress=50.0,
            )
        elif event.event_type == "task_completed":
            dur = event.data.get("execution_time_sec", 0.0)
            latency_us = dur * 1_000_000
            await self.update_agent(
                agent_id=agent_id,
                instruction=f"✅ Task '{node_id}' finished in {dur:.4f}s",
                status="COMPLETED",
                progress=100.0,
                latency=latency_us,
            )
        elif event.event_type == "task_failed":
            err = event.data.get("error", "Error")
            await self.update_agent(
                agent_id=agent_id,
                instruction=f"❌ Failed: {err}",
                status="FAILED",
                progress=100.0,
            )
        elif event.event_type == "pipeline_completed":
            await self.set_master_directive(
                f"🎉 GhostFlow Pipeline '{event.pipeline_name}' completed in {event.data.get('duration_sec', 0):.3f}s!"
            )
