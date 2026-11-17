"""Runtime simulation state and end-of-turn snapshot models."""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.aliases import (
    ConnectionKey,
    DroneCount,
    DroneId,
    TurnNumber,
    ZoneName,
)
from src.models.drone import DronesById, Movement
from src.models.enums import DroneStatus
from src.models.graph_utils import canonical_key

#: Zone name to drone count.
ZoneOccupancy: TypeAlias = dict[ZoneName, DroneCount]
#: Canonical connection key to drone count.
LinkUsage: TypeAlias = dict[ConnectionKey, DroneCount]
#: Zone name to maximum capacity.
ZoneCapacities: TypeAlias = dict[ZoneName, int | None]
#: Canonical connection key to maximum capacity.
LinkCapacities: TypeAlias = dict[ConnectionKey, int]


class TurnEvent(BaseModel):
    """One printed event for a drone on a turn.

    Exactly one target is set: ``zone`` for a zone visit, or
    ``from_zone``/``to_zone`` for a connection traversal.
    """

    drone_id: DroneId
    zone: ZoneName | None = None
    from_zone: ZoneName | None = None
    to_zone: ZoneName | None = None

    @model_validator(mode="after")
    def _validate_target(self) -> TurnEvent:
        """Require either a zone or a complete connection traversal."""
        has_zone = self.zone is not None
        has_connection = (
            self.from_zone is not None and self.to_zone is not None
        )
        has_partial_connection = (
            (self.from_zone is None) != (self.to_zone is None)
        )
        if has_partial_connection:
            raise ValueError(
                "connection traversal requires both endpoints"
            )
        if has_zone and has_connection:
            raise ValueError(
                "turn event cannot report both zone and connection"
            )
        if not has_zone and not has_connection:
            raise ValueError(
                "turn event requires either zone or from_zone/to_zone"
            )
        return self

    @property
    def kind(self) -> Literal["zone", "connection"]:
        """Kind of target this event reports."""
        return "zone" if self.zone is not None else "connection"


class DronePosition(BaseModel):
    """Position of a drone at the end of a turn."""

    zone: ZoneName | None = None
    connection: ConnectionKey | None = None
    status: DroneStatus = DroneStatus.WAITING

    @field_validator("connection")
    @classmethod
    def _canonicalize_connection(
        cls, connection: ConnectionKey | None
    ) -> ConnectionKey | None:
        """Normalize the undirected edge key to ``(zone_a, zone_b)``."""
        if connection is None:
            return None
        return canonical_key(*connection)

    @model_validator(mode="after")
    def _validate_target(self) -> DronePosition:
        """Require exactly one of zone or connection."""
        has_zone = self.zone is not None
        has_connection = self.connection is not None
        if has_zone == has_connection:
            raise ValueError(
                "drone position requires either zone or connection"
            )
        return self


#: Drone id to end-of-turn position.
DronePositions: TypeAlias = dict[DroneId, DronePosition]


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
            event.zone
            for event in self.events
            if event.zone is not None
        }


class SimulationState(BaseModel):
    """Mutable fleet state during replay."""

    turn: TurnNumber = 0
    drones: DronesById = Field(default_factory=dict)
    completed_drones: set[DroneId] = Field(default_factory=set)
