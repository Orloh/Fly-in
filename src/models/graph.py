"""Graph model combining zones and connections for pathfinding."""

from __future__ import annotations

from functools import cached_property

from pydantic import BaseModel, Field

from src.models.connection import Connection
from src.models.zone import Zone


class Graph(BaseModel):
    """Runtime graph representation with an adjacency index.

    ``zones`` and ``connections`` are the source of truth; ``adjacency``
    is derived lazily for efficient neighbor lookups during pathfinding.
    """

    zones: dict[str, Zone]
    connections: dict[tuple[str, str], Connection] = Field(
        default_factory=dict
    )

    @cached_property
    def adjacency(self) -> dict[str, list[str]]:
        """Map each zone name to its list of reachable neighbor names."""
        adj: dict[str, list[str]] = {name: [] for name in self.zones}
        for zone_a, zone_b in self.connections:
            adj[zone_a].append(zone_b)
            adj[zone_b].append(zone_a)
        return adj

    def neighbors(self, zone_name: str) -> list[str]:
        """Names of all zones directly connected to ``zone_name``."""
        return self.adjacency.get(zone_name, [])

    def connection_between(
        self, zone_a: str, zone_b: str
    ) -> Connection | None:
        """The connection linking two zones, if any."""
        if zone_a <= zone_b:
            key = (zone_a, zone_b)
        else:
            key = (zone_b, zone_a)
        return self.connections.get(key)
