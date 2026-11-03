"""
FlowContext - Execution context shared across TaskNodes in a GhostFlow pipeline.
"""

from typing import Any, Dict, Optional
import time


class FlowContext:
    """Stores shared state, intermediate results, and metadata across pipeline execution."""

    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        self._data: Dict[str, Any] = dict(initial_data or {})
        self._results: Dict[str, Any] = {}
        self._artifacts: Dict[str, Any] = {}
        self._node_timings: Dict[str, float] = {}
        self.created_at = time.time()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def store_result(self, node_id: str, result: Any, execution_time_sec: float = 0.0) -> None:
        self._results[node_id] = result
        self._node_timings[node_id] = execution_time_sec

    def get_result(self, node_id: str, default: Any = None) -> Any:
        return self._results.get(node_id, default)

    def store_artifact(self, name: str, artifact: Any) -> None:
        self._artifacts[name] = artifact

    def get_artifact(self, name: str, default: Any = None) -> Any:
        return self._artifacts.get(name, default)

    @property
    def results(self) -> Dict[str, Any]:
        return dict(self._results)

    @property
    def artifacts(self) -> Dict[str, Any]:
        return dict(self._artifacts)

    @property
    def timings(self) -> Dict[str, float]:
        return dict(self._node_timings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": dict(self._data),
            "results": dict(self._results),
            "artifacts": dict(self._artifacts),
            "timings": dict(self._node_timings),
        }
