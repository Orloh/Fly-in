"""Weighted shortest-path planning for the Fly-in simulation.

``find_path`` computes the cheapest start-to-goal route under the map's
zone-type entry costs (normal/priority = 1, restricted = 2, blocked =
impassable), preferring routes through priority zones when they tie on
total cost. It returns the ordered zone names from start to goal
inclusive, or ``None`` when the goal is unreachable.

New CBS low-level functions:
- ``dist_to_goal``: reverse Dijkstra heuristic table
- ``find_path_timed``: time-expanded A* with constraints
"""

from __future__ import annotations

import heapq
from typing import TypeAlias

from src.models import Graph, Zone, ZoneType

#: A TimedRoute is an ordered list of (zone, arrival_turn) pairs,
# start to goal inclusive.
TimedRoute: TypeAlias = list[tuple[str, int]]
#: VertexConstraint(zone, turn) — never occupy that zone at that turn.
VertexConstraint: TypeAlias = tuple[str, int]
#: LinkConstraint(canonical_link, turn) — never be on that link
#: during that turn.
LinkConstraint: TypeAlias = tuple[tuple[str, str], int]

#: Heuristic table: zone -> min travel time to goal (reverse Dijkstra).
Heuristic: TypeAlias = dict[str, int | float]


#: Turn cost of entering a zone, keyed by zone type (blocked = infinite).
_ZONE_COSTS: dict[ZoneType, int | float] = {
    ZoneType.NORMAL: 1,
    ZoneType.PRIORITY: 1,
    ZoneType.RESTRICTED: 2,
    ZoneType.BLOCKED: float("inf"),
}

#: Dijkstra queue entry: (cost, negated priority count, zone name).
_QueueEntry: TypeAlias = tuple[int | float, int, str]


def dist_to_goal(graph: Graph, goal: str) -> Heuristic:
    """Reverse Dijkstra from goal to all zones.

    Edge weight u->v = enter_cost(v). Returns dict[zone, min_turns_to_goal].
    Goal zone has distance 0. Blocked zones = inf.
    """
    raise NotImplementedError("dist_to_goal not yet implemented")


def find_path_timed(
    graph: Graph,
    start: str,
    goal: str,
    vertex_constraints: set[VertexConstraint],
    link_constraints: set[LinkConstraint],
    start_turn: int,
    horizon: int,
    dist: Heuristic,
) -> TimedRoute | None:
    """Time-expanded A* returning earliest feasible arrival route.

    State = (zone, turn). Start = (start, start_turn). Goal = any (goal, t).
    Successors: wait -> (z, t+1), move -> (w, t+enter_cost(w)).
    Constraints prune states/transitions. Heuristic f = turn + dist[zone].
    Returns list[(zone, arrival_turn)] or None if no route within horizon.
    """
    raise NotImplementedError("find_path_timed not yet implemented")


# --- Legacy find_path (used by engine.py until Phase 4) ---

#: A route is an ordered list of zone names, start to goal inclusive.
Route: TypeAlias = list[str]


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
