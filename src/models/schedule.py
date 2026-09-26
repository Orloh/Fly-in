"""Schedule domain models produced by the CBS planner."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.graph import Graph
from src.models.graph_utils import canonical_key


class ScheduledAction(BaseModel):
    """One timed action for a drone (WAIT or MOVE)."""

    kind: str
    turn: int
    from_zone: str
    to_zone: str
    turns_required: int = 1


class Schedule(BaseModel):
    """Optimal-makespan plan: per-drone timed action lists."""

    actions: dict[int, list[ScheduledAction]] = Field(default_factory=dict)
    makespan: int = 0
    graph: Graph

    def _occupancy(
        self,
    ) -> tuple[
        dict[tuple[str, int], int],
        dict[tuple[tuple[str, str], int], int],
    ]:
        """zone_time[(z,t)] and link_time[(canon,t)] from the actions.

        Matches the planner's occupancy model: a drone occupies its
        arrival zone at the arrival turn and its link during transit.
        """
        zone_time: dict[tuple[str, int], int] = {}
        link_time: dict[tuple[tuple[str, str], int], int] = {}
        for drone_actions in self.actions.values():
            for action in drone_actions:
                if action.kind == "WAIT":
                    zone_time[(action.from_zone, action.turn)] = (
                        zone_time.get((action.from_zone, action.turn), 0) + 1
                    )
                else:
                    arrival = action.turn + action.turns_required
                    zone_time[(action.to_zone, arrival)] = (
                        zone_time.get((action.to_zone, arrival), 0) + 1
                    )
                    link = canonical_key(action.from_zone, action.to_zone)
                    for t in range(
                        action.turn, action.turn + action.turns_required
                    ):
                        link_time[(link, t)] = link_time.get((link, t), 0) + 1
        return zone_time, link_time

    def is_conflict_free(self) -> bool:
        """Whether no zone/link exceeds capacity at any turn."""
        zone_time, link_time = self._occupancy()
        for (zone_name, turn), count in zone_time.items():
            zone = self.graph.zones.get(zone_name)
            if zone is None or zone.capacity is None:
                continue
            if count > zone.capacity:
                return False
        for (link, turn), count in link_time.items():
            connection = self.graph.connections.get(link)
            if connection is None:
                continue
            if count > connection.max_link_capacity:
                return False
        return True

    def occupies_goal_after_arrival(self) -> bool:
        """Whether arrived drones keep occupying finite-capacity goals.

        A drone whose goal is a finite-capacity zone is parked there for
        all turns >= arrival, so it must not be exceeded by arrivals at
        later turns.
        """
        zone_time, _ = self._occupancy()
        for (zone_name, turn), count in zone_time.items():
            zone = self.graph.zones.get(zone_name)
            if zone is None or zone.capacity is None:
                continue
            if count > zone.capacity:
                return False
        return True
