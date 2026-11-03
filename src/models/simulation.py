"""Runtime simulation state and end-of-turn snapshot models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.models.drone import Drone, Movement
from src.models.enums import DroneStatus


class TurnEvent(BaseModel):
    """One printed event for a drone on a turn."""

    drone_id: int
    kind: Literal["zone", "connection"]
    label: str


class DronePosition(BaseModel):
    """Logical position of a drone at the end of a turn."""

    zone: str | None = None
    connection: tuple[str, str] | None = None
    status: DroneStatus = DroneStatus.WAITING


class TurnSnapshot(BaseModel):
    """Logical end-of-turn snapshot used for output and diagnostics.

    ``events`` are the tokens that should be printed for this turn.
    ``positions`` holds every drone's logical position after the turn.
    ``zone_occupancy`` and ``link_usage`` are derived from those positions.
    ``moved_zones`` contains the zones shown as zone tokens.
    """

    turn_number: int
    movements: list[Movement] = Field(default_factory=list)
    events: list[TurnEvent] = Field(default_factory=list)
    positions: dict[int, DronePosition] = Field(default_factory=dict)
    zone_occupancy: dict[str, int] = Field(default_factory=dict)
    link_usage: dict[tuple[str, str], int] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    moved_zones: set[str] = Field(default_factory=set)
    zone_capacities: dict[str, int | None] = Field(default_factory=dict)
    link_capacities: dict[tuple[str, str], int] = Field(default_factory=dict)


#: Backwards-compatible alias for code that used the old result name.
TurnResult = TurnSnapshot


class SimulationState(BaseModel):
    """Mutable fleet state during replay."""

    turn: int = 0
    drones: dict[int, Drone] = Field(default_factory=dict)
    link_usage: dict[tuple[str, str], int] = Field(default_factory=dict)
    completed_drones: set[int] = Field(default_factory=set)
