"""Weighted shortest-path planning for the Fly-in simulation.

``find_path`` computes the cheapest start-to-goal route under the map's
zone-type entry costs (normal/priority = 1, restricted = 2, blocked =
impassable), preferring routes through priority zones when they tie on
total cost. It returns the ordered zone names from start to goal
inclusive, or ``None`` when the goal is unreachable.
"""

from __future__ import annotations

import heapq
from typing import TypeAlias

from src.models import Graph, Zone, ZoneType

#: A route is an ordered list of zone names, start to goal inclusive.
Route: TypeAlias = list[str]

#: Turn cost of entering a zone, keyed by zone type (blocked = infinite).
_ZONE_COSTS: dict[ZoneType, int | float] = {
    ZoneType.NORMAL: 1,
    ZoneType.PRIORITY: 1,
    ZoneType.RESTRICTED: 2,
    ZoneType.BLOCKED: float("inf"),
}

#: Dijkstra queue entry: (cost, negated priority count, zone name).
_QueueEntry: TypeAlias = tuple[int | float, int, str]


def find_path(graph: Graph, start: str, goal: str) -> Route | None:
    """Return the cheapest start-to-goal route, or None if unreachable.

    A zone's entry cost is ``_ZONE_COSTS`` keyed by its type; blocked
    zones are never entered. Equal-cost routes prefer more priority
    zones. Returns ``[start]`` when ``start == goal``.
    """
    if start == goal:
        return [start]

    priority_queue: list[_QueueEntry] = [(0, 0, start)]
    breadcrumbs: dict[str, str] = {}
    zone_reach: dict[str, tuple[int | float, int]] = {start: (0, 0)}

    while priority_queue:
        cost, priority, zone_name = heapq.heappop(priority_queue)

        if (cost, priority) != zone_reach[zone_name]:
            continue

        if zone_name == goal:
            route: Route = []
            current = goal
            while current != start:
                route.append(current)
                current = breadcrumbs[current]
            route.append(start)
            route.reverse()
            return route

        for adj_name in graph.neighbors(zone_name):
            adj_zone = graph.zones[adj_name]

            if adj_zone.zone_type == ZoneType.BLOCKED:
                continue

            path_cost = cost + _enter_cost(adj_zone)
            if adj_zone.zone_type == ZoneType.PRIORITY:
                path_priority = priority - 1
            else:
                path_priority = priority

            best_known = zone_reach.get(adj_name)
            if best_known is None or (path_cost, path_priority) < best_known:
                zone_reach[adj_name] = (path_cost, path_priority)
                breadcrumbs[adj_name] = zone_name
                heapq.heappush(
                    priority_queue, (path_cost, path_priority, adj_name)
                )

    return None


def _enter_cost(zone: Zone) -> int | float:
    """Return the turn cost of moving into ``zone``."""
    return _ZONE_COSTS[zone.zone_type]
