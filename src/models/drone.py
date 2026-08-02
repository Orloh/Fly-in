"""Drone and movement models tracking the fleet during simulation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.enums import DroneStatus


class Drone(BaseModel):
    """State of a single simulated drone."""

    id: int
    current_zone: str | None = None
    target_zone: str
    status: DroneStatus = DroneStatus.WAITING
    path: list[str] = Field(default_factory=list)
    turns_in_transit: int = 0
    transit_destination: str | None = None

    @property
    def arrived(self) -> bool:
        """Whether the drone has reached its target zone."""
        return self.status == DroneStatus.ARRIVED


class Movement(BaseModel):
    """A single drone movement announced on a simulation turn."""

    drone_id: int
    from_zone: str
    to_zone: str
    turns_required: int = 1
