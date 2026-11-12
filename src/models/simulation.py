"""Runtime simulation state and end-of-turn snapshot models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.models.aliases import (
    ConnectionKey,
    DroneId,
    TurnNumber,
    ZoneName,
)
from src.models.drone import Drone, Movement
from src.models.enums import DroneStatus

#: Zone name to drone count.
ZoneOccupancy = dict[ZoneName, int]
#: Canonical connection key to drone count.
LinkUsage = dict[ConnectionKey, int]
#: Zone name to maximum capacity.
ZoneCapacities = dict[ZoneName, int | None]
#: Canonical connection key to maximum capacity.
LinkCapacities = dict[ConnectionKey, int]


class TurnEvent(BaseModel):
    """One printed event for a drone on a turn."""

    drone_id: DroneId
    kind: Literal["zone", "connection"]
    label: str


class DronePosition(BaseModel):
    """Position of a drone at the end of a turn."""

    zone: ZoneName | None = None
    connection: ConnectionKey | None = None
    status: DroneStatus = DroneStatus.WAITING


#: Drone id to end-of-turn position.
DronePositions = dict[DroneId, DronePosition]


class TurnSnapshot(BaseModel):
    """End-of-turn snapshot used for output and diagnostics.

    ``events`` are the tokens that should be printed for this turn.
    ``positions`` holds every drone's position after the turn.
    ``zone_occupancy`` and ``link_usage`` are derived from those positions.
    ``moved_zones`` is derived from the zone events.
    """

    turn_number: TurnNumber
    movements: list[Movement] = Field(default_factory=list)
    events: list[TurnEvent] = Field(default_factory=list)
    positions: DronePositions = Field(default_factory=dict)
    zone_occupancy: ZoneOccupancy = Field(default_factory=dict)
    link_usage: LinkUsage = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    zone_capacities: ZoneCapacities = Field(default_factory=dict)
    link_capacities: LinkCapacities = Field(default_factory=dict)

    @property
    def moved_zones(self) -> set[ZoneName]:
        """Zones printed as zone tokens this turn."""
        return {
            event.label
            for event in self.events
            if event.kind == "zone"
        }


class SimulationState(BaseModel):
    """Mutable fleet state during replay."""

    turn: TurnNumber = 0
    drones: dict[DroneId, Drone] = Field(default_factory=dict)
    completed_drones: set[DroneId] = Field(default_factory=set)
