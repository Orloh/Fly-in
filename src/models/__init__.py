"""Data models for the Fly-in drone routing simulation.

This package exposes the domain schemas used by the parser, pathfinding
and simulation layers.
"""

from src.models.aliases import (
	ConnectionKey,
	DroneCount,
	DroneId,
	LineNumber,
	LinkTurn,
	Metadata,
	TurnNumber,
	ZoneName,
	ZoneTurn,
)
from src.models.connection import Connection
from src.models.drone import Drone, DroneFleet, DronesById, Movement
from src.models.enums import DroneStatus, ZoneType
from src.models.graph import ConnectionMap, Graph, ZoneMap
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
	"ConnectionMap",
	"Drone",
	"DroneCount",
	"DroneFleet",
	"DroneId",
	"DronePosition",
	"DronePositions",
	"DronesById",
	"DroneStatus",
	"Graph",
	"LineNumber",
	"LinkCapacities",
	"LinkTurn",
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
	"ZoneMap",
	"ZoneName",
	"ZoneOccupancy",
	"ZoneTurn",
	"ZoneType",
	"canonical_key",
]
