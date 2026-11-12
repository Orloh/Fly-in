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
#: Simulation turn number.
TurnNumber: TypeAlias = int
#: Source-file line number used in parse diagnostics.
LineNumber: TypeAlias = int
#: Raw parser metadata, stored as strings before domain conversion.
Metadata: TypeAlias = dict[str, str]
