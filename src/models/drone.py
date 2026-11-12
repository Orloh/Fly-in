"""Drone and movement models tracking the fleet during simulation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.aliases import DroneId, ZoneName
from src.models.enums import DroneStatus
from src.models.schedule import ScheduledAction


class Drone(BaseModel):
    """State of a single simulated drone."""

    id: DroneId
    current_zone: ZoneName | None = None
    target_zone: ZoneName
    status: DroneStatus = DroneStatus.WAITING
    schedule: list[ScheduledAction] = Field(default_factory=list)
    schedule_index: int = 0
    transit_from: ZoneName | None = None
    transit_destination: ZoneName | None = None
    turns_remaining: int = 0
    blocked_reason: str | None = None


class Movement(BaseModel):
    """A single drone movement announced on a simulation turn."""

    drone_id: DroneId
    from_zone: ZoneName
    to_zone: ZoneName
    turns_required: int = 1
