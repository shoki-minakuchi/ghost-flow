# 👻 GhostFlow

> **Lightweight, Sub-Millisecond Asynchronous DAG Pipeline & Event-Driven Orchestrator for Autonomous Agent Swarms**

---

## ⚡ Overview

`ghost-flow` is a high-performance, zero-overhead task execution and workflow engine specifically designed for autonomous LLM agent swarms. It allows complex agent processes to be represented as Directed Acyclic Graphs (DAGs) and executed asynchronously with maximum concurrency.

### Key Capabilities
- **Directed Acyclic Graph (DAG) Execution**: Declarative dependencies between agent tasks with automatic cycle detection and topological scheduling.
- **Event-Driven Pub/Sub Bus**: Emits sub-millisecond lifecycle events (`task_scheduled`, `task_running`, `task_completed`, `task_failed`).
- **Live Swarm Cockpit Bridge**: Direct integration with [GhostGym](https://github.com/shoki-minakuchi/ghost-gym) Web Cockpit (`ws://localhost:8765/ws`), broadcasting real-time progress, latency telemetry, and dynamic sub-agent topologies.
- **Production Stealth & Zero Bloat**: Pure Python async engine with minimal dependencies (`aiohttp`).

---

## 🏗️ Architecture

```
                      +-----------------------------------+
                      |   🧠 Antigravity LLM Commander     |
                      +-----------------+-----------------+
                                        |
                             WebSocket Telemetry
                                        v
                       +----------------------------------+
                       |   🗺️ GhostGym Swarm Cockpit      |
                       |       (Live Topology Map)        |
                       +----------------+-----------------+
                                        ^
                                        |
  +-------------------------------------+-------------------------------------+
  |                             👻 GhostFlow Engine                           |
  |                                                                           |
  |   +-------------------+    +--------------------+    +----------------+   |
  |   |   FlowPipeline    |--->|    DAG Scheduler   |--->|  EventManager  |   |
  |   +-------------------+    +--------------------+    +----------------+   |
  |             |                        |                       |            |
  |             v                        v                       v            |
  |      [TaskNode: A]            [TaskNode: B]            [TaskNode: C]      |
  |   (Flow-Architect)           (Flow-Engine)             (Flow-QA)          |
  +---------------------------------------------------------------------------+
```

---

## 🚀 Quick Start

### Installation

```bash
pip install -e .
```

### Basic Example

```python
import asyncio
from ghost_flow.core.pipeline import FlowPipeline
from ghost_flow.core.node import TaskNode

async def main():
    pipeline = FlowPipeline(name="agent-task-swarm")

    # Define tasks
    node1 = TaskNode("audit", lambda ctx: "Audit Passed")
    node2 = TaskNode("compile", lambda ctx: "Artifact Built", depends_on=["audit"])
    node3 = TaskNode("verify", lambda ctx: "Verification 100%", depends_on=["compile"])

    pipeline.add_nodes([node1, node2, node3])
    results = await pipeline.run()
    print("Execution results:", results)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🧪 Testing

```bash
pytest -v
```

---

## 📜 License

MIT License. Designed for next-generation autonomous AI pair programming.
