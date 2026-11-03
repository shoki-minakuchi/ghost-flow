"""
FlowPipeline - Asynchronous DAG workflow scheduler and execution engine.
"""

import asyncio
from collections import defaultdict, deque
import time
from typing import Any, Dict, List, Optional, Set
from ghost_flow.core.context import FlowContext
from ghost_flow.core.events import EventManager
from ghost_flow.core.node import TaskNode, NodeStatus


class FlowPipeline:
    """Asynchronous Directed Acyclic Graph (DAG) pipeline executor."""

    def __init__(
        self,
        name: str = "ghost-flow-pipeline",
        fail_fast: bool = True,
        max_concurrency: Optional[int] = None,
        event_manager: Optional[EventManager] = None,
    ):
        self.name = name
        self.fail_fast = fail_fast
        self.max_concurrency = max_concurrency
        self.event_manager = event_manager or EventManager()
        self.nodes: Dict[str, TaskNode] = {}
        self.is_running = False

    def add_node(self, node: TaskNode) -> "FlowPipeline":
        if node.node_id in self.nodes:
            raise ValueError(f"TaskNode with ID '{node.node_id}' already exists in pipeline '{self.name}'")
        self.nodes[node.node_id] = node
        return self

    def add_nodes(self, nodes: List[TaskNode]) -> "FlowPipeline":
        for n in nodes:
            self.add_node(n)
        return self

    def validate_dag(self) -> None:
        """Validates that all dependencies exist and graph contains no cycles."""
        for node_id, node in self.nodes.items():
            for dep in node.depends_on:
                if dep not in self.nodes:
                    raise ValueError(f"TaskNode '{node_id}' depends on non-existent node '{dep}'")

        # Kahn's algorithm for cycle detection
        in_degree: Dict[str, int] = {nid: len(n.depends_on) for nid, n in self.nodes.items()}
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        visited_count = 0

        # Adjacency list: parent -> children
        children: Dict[str, List[str]] = defaultdict(list)
        for nid, node in self.nodes.items():
            for dep in node.depends_on:
                children[dep].append(nid)

        while queue:
            curr = queue.popleft()
            visited_count += 1
            for child in children[curr]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if visited_count != len(self.nodes):
            raise ValueError(f"Pipeline '{self.name}' contains a circular dependency (cycle detected)")

    async def run(self, context: Optional[FlowContext] = None) -> Dict[str, Any]:
        """Runs the pipeline asynchronously, respecting dependencies and concurrency limits."""
        self.validate_dag()
        ctx = context or FlowContext()
        self.is_running = True
        start_time = time.perf_counter()

        await self.event_manager.emit(
            "pipeline_started",
            pipeline_name=self.name,
            total_nodes=len(self.nodes),
        )

        # Build dependencies & dependents maps
        remaining_deps: Dict[str, Set[str]] = {nid: set(n.depends_on) for nid, n in self.nodes.items()}
        dependents: Dict[str, List[str]] = defaultdict(list)
        for nid, node in self.nodes.items():
            for dep in node.depends_on:
                dependents[dep].append(nid)

        completed_nodes: Set[str] = set()
        failed_nodes: Set[str] = set()
        skipped_nodes: Set[str] = set()
        running_tasks: Dict[asyncio.Task, str] = {}

        # Concurrency throttle
        semaphore = asyncio.Semaphore(self.max_concurrency) if self.max_concurrency else None

        async def _run_single_node(node: TaskNode) -> Any:
            if semaphore:
                async with semaphore:
                    return await node.execute(ctx)
            return await node.execute(ctx)

        # Initial ready nodes
        ready_queue = deque([nid for nid, deps in remaining_deps.items() if len(deps) == 0])

        try:
            while len(completed_nodes) + len(failed_nodes) + len(skipped_nodes) < len(self.nodes):
                # Schedule all ready nodes
                while ready_queue:
                    next_nid = ready_queue.popleft()
                    node = self.nodes[next_nid]
                    node.status = NodeStatus.READY
                    await self.event_manager.emit(
                        "task_ready",
                        pipeline_name=self.name,
                        node_id=next_nid,
                        agent_role=node.agent_role,
                        description=node.description,
                    )

                    await self.event_manager.emit(
                        "task_running",
                        pipeline_name=self.name,
                        node_id=next_nid,
                        agent_role=node.agent_role,
                        description=node.description,
                    )
                    t = asyncio.create_task(_run_single_node(node))
                    running_tasks[t] = next_nid

                if not running_tasks:
                    # If nothing is running and uncompleted nodes remain, remaining must be blocked by failed/skipped
                    for nid, node in self.nodes.items():
                        if nid not in completed_nodes and nid not in failed_nodes and nid not in skipped_nodes:
                            node.status = NodeStatus.SKIPPED
                            skipped_nodes.add(nid)
                            await self.event_manager.emit(
                                "task_skipped",
                                pipeline_name=self.name,
                                node_id=nid,
                                reason="Parent dependency failed or skipped",
                            )
                    break

                # Wait for any running task to finish
                done, _ = await asyncio.wait(
                    running_tasks.keys(),
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    nid = running_tasks.pop(task)
                    node = self.nodes[nid]
                    if task.exception() is not None:
                        failed_nodes.add(nid)
                        await self.event_manager.emit(
                            "task_failed",
                            pipeline_name=self.name,
                            node_id=nid,
                            agent_role=node.agent_role,
                            error=str(task.exception()),
                            attempts=node.attempts,
                        )
                        if self.fail_fast:
                            # Cancel running tasks
                            for running_t in running_tasks:
                                running_t.cancel()
                            self.is_running = False
                            raise task.exception()
                    else:
                        completed_nodes.add(nid)
                        await self.event_manager.emit(
                            "task_completed",
                            pipeline_name=self.name,
                            node_id=nid,
                            agent_role=node.agent_role,
                            result=str(node.result)[:100],
                            execution_time_sec=node.execution_time_sec,
                        )
                        # Notify dependents
                        for dep_child in dependents[nid]:
                            if dep_child in remaining_deps:
                                remaining_deps[dep_child].discard(nid)
                                if len(remaining_deps[dep_child]) == 0:
                                    ready_queue.append(dep_child)

            total_duration = time.perf_counter() - start_time
            await self.event_manager.emit(
                "pipeline_completed",
                pipeline_name=self.name,
                duration_sec=total_duration,
                completed_count=len(completed_nodes),
                failed_count=len(failed_nodes),
                skipped_count=len(skipped_nodes),
            )
            self.is_running = False
            return ctx.results

        except Exception as e:
            self.is_running = False
            total_duration = time.perf_counter() - start_time
            await self.event_manager.emit(
                "pipeline_failed",
                pipeline_name=self.name,
                duration_sec=total_duration,
                error=str(e),
            )
            raise
