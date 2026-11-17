"""Graph model combining zones and connections for pathfinding."""

from __future__ import annotations

from functools import cached_property
from typing import TypeAlias

from pydantic import BaseModel, Field

from src.models.aliases import ConnectionKey, ZoneName
from src.models.connection import Connection
from src.models.zone import Zone

#: Zone name to validated zone.
ZoneMap: TypeAlias = dict[ZoneName, Zone]
#: Canonical connection key to validated connection.
ConnectionMap: TypeAlias = dict[ConnectionKey, Connection]
#: Zone name to adjacent zone names.
Adjacency: TypeAlias = dict[ZoneName, list[ZoneName]]


class Graph(BaseModel):
    """Runtime graph representation with an adjacency index.

    ``zones`` and ``connections`` are the source of truth; ``adjacency``
    is derived lazily for efficient neighbor lookups during pathfinding.
    """

    zones: ZoneMap
    connections: ConnectionMap = Field(default_factory=dict)

    @cached_property
    def adjacency(self) -> Adjacency:
        """Map each zone name to its list of reachable neighbor names.

        Returns:
            Zone name to list of neighbor names.
        """
        adj: Adjacency = {name: [] for name in self.zones}
        for zone_a, zone_b in self.connections:
            adj[zone_a].append(zone_b)
            adj[zone_b].append(zone_a)
        return adj

    def neighbors(self, zone_name: ZoneName) -> list[ZoneName]:
        """Names of all zones directly connected to ``zone_name``.

        Args:
            zone_name: The zone whose neighbors to look up.

        Returns:
            The connected zone names, or an empty list.
        """
        return self.adjacency.get(zone_name, [])
