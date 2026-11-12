"""Data models for the Fly-in drone routing simulation.

This package exposes the domain schemas used by the parser, pathfinding
and simulation layers.
"""

from src.models.aliases import (
    ConnectionKey,
    DroneId,
    LineNumber,
    Metadata,
    TurnNumber,
    ZoneName,
)
from src.models.connection import Connection
from src.models.drone import Drone, Movement
from src.models.enums import DroneStatus, ZoneType
from src.models.graph import Graph
from src.models.parsing import ParsedConnection, ParsedMap, ParsedZone
from src.models.schedule import Schedule, ScheduledAction
from src.models.simulation import (
    DronePosition,
    DronePositions,
    LinkCapacities,
    LinkUsage,
    SimulationState,
    TurnEvent,
    TurnSnapshot,
    ZoneCapacities,
    ZoneOccupancy,
)
from src.models.zone import Zone
from src.models.graph_utils import canonical_key

__all__ = [
    "Connection",
    "ConnectionKey",
    "Drone",
    "DroneId",
    "DronePosition",
    "DronePositions",
    "DroneStatus",
    "Graph",
    "LineNumber",
    "LinkCapacities",
    "LinkUsage",
    "Metadata",
    "Movement",
    "ParsedConnection",
    "ParsedMap",
    "ParsedZone",
    "Schedule",
    "ScheduledAction",
    "SimulationState",
    "TurnEvent",
    "TurnNumber",
    "TurnSnapshot",
    "Zone",
    "ZoneCapacities",
    "ZoneName",
    "ZoneOccupancy",
    "ZoneType",
    "canonical_key",
]
