"""
GhostFlow - Lightweight asynchronous DAG pipeline & event-driven orchestrator for autonomous agent swarms.
"""

from ghost_flow.core.context import FlowContext
from ghost_flow.core.node import TaskNode, NodeStatus
from ghost_flow.core.pipeline import FlowPipeline
from ghost_flow.core.events import EventManager, FlowEvent

__version__ = "0.1.0"
__all__ = [
    "FlowContext",
    "TaskNode",
    "NodeStatus",
    "FlowPipeline",
    "EventManager",
    "FlowEvent",
]
