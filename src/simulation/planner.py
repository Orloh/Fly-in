"""Conflict-Based Search high-level planner.

``Planner`` computes a makespan-optimal ``Schedule`` for a drone fleet
using Conflict-Based Search: a constraint tree over capacity conflicts,
solved by repeated low-level ``find_path_timed`` calls. The schedule is
computed once, offline, and replayed by the engine.
"""

from __future__ import annotations

from src.models import Drone, Graph
from src.models.schedule import Schedule


class Planner:
    """Optimal-makespan fleet planner via Conflict-Based Search."""

    def __init__(self, graph: Graph) -> None:
        """Store the graph for low-level searches."""
        self.graph = graph
        raise NotImplementedError("Planner not yet implemented")

    def plan(self, drones: list[Drone]) -> tuple[Schedule, list[Drone]]:
        """Compute an optimal Schedule; return (schedule, blocked drones).

        Drones with no spatial route are marked BLOCKED with a
        ``blocked_reason`` and excluded from the search.
        """
        raise NotImplementedError("plan not yet implemented")
