"""Runtime simulation state models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.drone import Drone
from src.models.drone import Movement


class TurnResult(BaseModel):
    """The outcome of a single simulation turn.

    ``zone_occupancy`` is the projected end-of-turn occupancy, after all
    launches and normal arrivals for this turn have been applied.
    ``moved_zones`` contains the zones that appear as zone tokens this
    turn, and ``capacities`` maps those zones to their maximum capacity.
    ``in_flight`` and ``restricted_arrivals`` describe continuing and
    final restricted transits for output formatting.
    """

    turn_number: int
    movements: list[Movement] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    zone_occupancy: dict[str, int] = Field(default_factory=dict)
    moved_zones: set[str] = Field(default_factory=set)
    capacities: dict[str, int | None] = Field(default_factory=dict)
    in_flight: dict[int, str] = Field(default_factory=dict)
    restricted_arrivals: dict[int, str] = Field(default_factory=dict)


class SimulationState(BaseModel):
    """Mutable fleet state during replay."""

    turn: int = 0
    drones: dict[int, Drone] = Field(default_factory=dict)
    link_usage: dict[tuple[str, str], int] = Field(default_factory=dict)
    completed_drones: set[int] = Field(default_factory=set)
