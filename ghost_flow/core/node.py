"""
TaskNode - Executable task unit within a GhostFlow DAG pipeline.
"""

import asyncio
from enum import Enum
import inspect
import time
from typing import Any, Callable, Dict, List, Optional
from ghost_flow.core.context import FlowContext


class NodeStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class TaskNode:
    """Represents a discrete executable task assigned to an agent in a DAG workflow."""

    def __init__(
        self,
        node_id: str,
        handler: Callable[[FlowContext], Any],
        depends_on: Optional[List[str]] = None,
        agent_role: str = "Flow-Worker",
        description: str = "",
        retries: int = 0,
        timeout_sec: Optional[float] = None,
    ):
        self.node_id = str(node_id)
        self.handler = handler
        self.depends_on: List[str] = list(depends_on or [])
        self.agent_role = agent_role
        self.description = description or f"Execute task '{node_id}'"
        self.retries = max(0, retries)
        self.timeout_sec = timeout_sec

        self.status: NodeStatus = NodeStatus.PENDING
        self.result: Any = None
        self.error: Optional[Exception] = None
        self.attempts: int = 0
        self.execution_time_sec: float = 0.0

    async def execute(self, context: FlowContext) -> Any:
        """Executes the node handler with retry and timeout mechanisms."""
        self.status = NodeStatus.RUNNING
        self.attempts = 0
        start_time = time.perf_counter()

        last_exc: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            self.attempts = attempt + 1
            try:
                if inspect.iscoroutinefunction(self.handler):
                    task_coro = self.handler(context)
                else:
                    task_coro = asyncio.to_thread(self.handler, context)

                if self.timeout_sec is not None and self.timeout_sec > 0:
                    self.result = await asyncio.wait_for(task_coro, timeout=self.timeout_sec)
                else:
                    self.result = await task_coro

                self.execution_time_sec = time.perf_counter() - start_time
                self.status = NodeStatus.COMPLETED
                self.error = None
                context.store_result(self.node_id, self.result, self.execution_time_sec)
                return self.result

            except Exception as exc:
                last_exc = exc
                if attempt < self.retries:
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue

        self.execution_time_sec = time.perf_counter() - start_time
        self.status = NodeStatus.FAILED
        self.error = last_exc
        raise last_exc or RuntimeError(f"TaskNode '{self.node_id}' failed with unknown error")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "agent_role": self.agent_role,
            "description": self.description,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "attempts": self.attempts,
            "execution_time_sec": self.execution_time_sec,
            "has_error": self.error is not None,
        }
