"""Runtime simulation state models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.drone import Drone
from src.models.drone import Movement
from src.models.enums import DroneStatus


class TurnResult(BaseModel):
    """The outcome of a single simulation turn."""

    turn_number: int
    movements: list[Movement] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class SimulationState(BaseModel):
    """Mutable snapshot of the fleet and occupancy across turns."""

    turn: int = 0
    drones: dict[int, Drone] = Field(default_factory=dict)
    zone_occupancy: dict[str, int] = Field(default_factory=dict)
    link_usage: dict[tuple[str, str], int] = Field(default_factory=dict)
    completed_drones: set[int] = Field(default_factory=set)

    def update_occupancy(self) -> None:
        """Recount drones per zone from their current positions.

        In-transit drones are excluded — they occupy no zone during
        traversal.
        """
        counts: dict[str, int] = {}
        for drone in self.drones.values():
            if drone.status == DroneStatus.IN_TRANSIT:
                continue
            zone = drone.current_zone
            if zone is None:
                continue
            counts[zone] = counts.get(zone, 0) + 1
        self.zone_occupancy = counts
