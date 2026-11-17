"""Semantic type aliases shared across the project.

These aliases make function signatures self-documenting without changing
the underlying runtime types.
"""

from __future__ import annotations

from typing import TypeAlias

#: Unique zone identifier in the map graph.
ZoneName: TypeAlias = str
#: Canonical undirected connection key, ordered as ``(zone_a, zone_b)``.
ConnectionKey: TypeAlias = tuple[ZoneName, ZoneName]
#: Unique drone identifier.
DroneId: TypeAlias = int
#: Number of drones occupying a zone, link, or turn.
DroneCount: TypeAlias = int
#: Simulation turn number.
TurnNumber: TypeAlias = int
#: A zone and the turn at which it is occupied.
ZoneTurn: TypeAlias = tuple[ZoneName, TurnNumber]
#: A canonical connection and the turn during which it is occupied.
LinkTurn: TypeAlias = tuple[ConnectionKey, TurnNumber]
#: Source-file line number used in parse diagnostics.
LineNumber: TypeAlias = int
#: Raw parser metadata, stored as strings before domain conversion.
Metadata: TypeAlias = dict[str, str]
