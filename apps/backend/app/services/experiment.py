from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class TaskMeasurement:
    task_id: str
    group: str
    elapsed_minutes: float
    completed: bool
    required_escalation: bool = False


def summarize_measurements(measurements: list[TaskMeasurement]) -> dict:
    groups: dict[str, list[TaskMeasurement]] = {}
    for item in measurements:
        groups.setdefault(item.group, []).append(item)
    result = {}
    for group, items in groups.items():
        result[group] = {
            "sample_count": len(items),
            "mean_resolution_minutes": round(mean(item.elapsed_minutes for item in items), 2),
            "completion_rate": round(sum(item.completed for item in items) / len(items), 2),
            "self_service_rate": round(sum(not item.required_escalation for item in items) / len(items), 2),
        }
    return {"experiment_kind": "internal_simulation", "groups": result}
