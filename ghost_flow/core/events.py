"""
EventManager - Asynchronous pub/sub event bus for GhostFlow execution lifecycles.
"""

import asyncio
from dataclasses import dataclass, field
import inspect
import time
from typing import Any, Callable, Dict, List, Optional


@dataclass
class FlowEvent:
    event_type: str
    pipeline_name: str
    node_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class EventManager:
    """Asynchronous event bus managing subscriptions and dispatch for workflow telemetry."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable[[FlowEvent], Any]]] = {}
        self._global_listeners: List[Callable[[FlowEvent], Any]] = []
        self._history: List[FlowEvent] = []

    def subscribe(self, event_type: str, callback: Callable[[FlowEvent], Any]) -> None:
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def subscribe_all(self, callback: Callable[[FlowEvent], Any]) -> None:
        self._global_listeners.append(callback)

    async def emit(self, event_type: str, pipeline_name: str, node_id: Optional[str] = None, **data) -> FlowEvent:
        event = FlowEvent(
            event_type=event_type,
            pipeline_name=pipeline_name,
            node_id=node_id,
            data=data,
            timestamp=time.time(),
        )
        self._history.append(event)

        targets = list(self._listeners.get(event_type, [])) + list(self._global_listeners)
        coros = []
        for cb in targets:
            try:
                if inspect.iscoroutinefunction(cb):
                    coros.append(cb(event))
                else:
                    cb(event)
            except Exception:
                pass

        if coros:
            await asyncio.gather(*coros, return_exceptions=True)

        return event

    @property
    def history(self) -> List[FlowEvent]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()
        self._listeners.clear()
        self._global_listeners.clear()
