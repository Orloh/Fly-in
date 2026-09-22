"""Weighted shortest-path planning for the Fly-in simulation.

Legacy ``find_path`` computes the cheapest start-to-goal route under the
map's zone-type entry costs. The CBS low-level search adds two timed
functions: ``dist_to_goal`` (reverse Dijkstra heuristic) and
``find_path_timed`` (time-expanded A* with constraints).
"""

from __future__ import annotations

import heapq
from typing import TypeAlias

from src.models import Graph, Zone, ZoneType, canonical_key

#: A (zone, arrival_turn) state in the time-expanded search space.
State: TypeAlias = tuple[str, int]
#: An ordered list of states from start to goal, inclusive.
TimedRoute: TypeAlias = list[State]
#: A forbidden (zone, turn) occupancy — structurally a State.
VertexConstraint: TypeAlias = State
#: A forbidden (canonical_link, turn) occupancy during a transit.
LinkConstraint: TypeAlias = tuple[tuple[str, str], int]
#: The constraint pair passed to the low-level search.
Constraints: TypeAlias = tuple[set[VertexConstraint], set[LinkConstraint]]
#: Heuristic table: zone -> min travel time to goal (reverse Dijkstra).
Heuristic: TypeAlias = dict[str, int | float]
#: Accumulated priority-zone count per search state.
PriorityCount: TypeAlias = dict[State, int]
#: Path reconstruction: state -> previous state (None for the start).
Breadcrumbs: TypeAlias = dict[State, State | None]
#: Best known g-score (turn) per state, for stale-entry pruning.
BestG: TypeAlias = dict[State, int]


#: Turn cost of entering a zone, keyed by zone type (blocked = infinite).
_ZONE_COSTS: dict[ZoneType, int | float] = {
    ZoneType.NORMAL: 1,
    ZoneType.PRIORITY: 1,
    ZoneType.RESTRICTED: 2,
    ZoneType.BLOCKED: float("inf"),
}

#: Reverse-Dijkstra queue entry: (distance, zone_name).
_QueueEntry: TypeAlias = tuple[int | float, str]

#: Timed A* queue entry: (f, -priority_count, turn, zone_name).
_TimedQueueEntry: TypeAlias = tuple[int | float, int, int, str]


def _reconstruct_path(
    breadcrumbs: Breadcrumbs, goal_state: State
) -> TimedRoute:
    """Rebuild the route by walking breadcrumbs from goal to start."""
    route: TimedRoute = []
    current: State | None = goal_state
    while current is not None:
        route.append(current)
        current = breadcrumbs[current]
    route.reverse()
    return route


def _is_link_blocked(
    link_key: tuple[str, str],
    start_turn: int,
    end_turn: int,
    link_constraints: set[LinkConstraint],
) -> bool:
    """Whether any transit turn in [start_turn, end_turn) is constrained."""
    for turn in range(start_turn, end_turn):
        if (link_key, turn) in link_constraints:
            return True
    return False


def _vertex_blocked(
    state: State, vertex_constraints: set[VertexConstraint]
) -> bool:
    """Whether ``state`` is vertex-constrained."""
    return state in vertex_constraints


def _push_state(
    pq: list[_TimedQueueEntry],
    breadcrumbs: Breadcrumbs,
    priority_count: PriorityCount,
    best_g: BestG,
    dist: Heuristic,
    state: State,
    prev_state: State | None,
    new_priority: int,
) -> None:
    """Enqueue ``state`` when it improves the best known g-score."""
    zone, turn = state
    if turn >= best_g.get(state, turn + 1):
        return
    best_g[state] = turn
    breadcrumbs[state] = prev_state
    priority_count[state] = new_priority
    f_score = turn + dist[zone]
    heapq.heappush(pq, (f_score, -new_priority, turn, zone))


def dist_to_goal(graph: Graph, goal: str) -> Heuristic:
    """Reverse Dijkstra from goal to all zones.

    Edge weight u->v = enter_cost(v). Returns dict[zone, min_turns_to_goal].
    Goal zone has distance 0. Blocked zones = inf.
    """
    heuristic_table: Heuristic = {
        zone_name: float("inf") for zone_name in graph.zones
    }
    heuristic_table[goal] = 0

    priority_queue: list[_QueueEntry] = [(0, goal)]

    while priority_queue:
        current_distance, current_zone_name = heapq.heappop(priority_queue)

        if current_distance > heuristic_table[current_zone_name]:
            continue

        for neighbor in graph.neighbors(current_zone_name):
            neighbor_zone = graph.zones[neighbor]

            if neighbor_zone.zone_type == ZoneType.BLOCKED:
                continue

            new_distance = current_distance + _enter_cost(
                graph.zones[current_zone_name]
            )

            if new_distance < heuristic_table[neighbor]:
                heuristic_table[neighbor] = new_distance
                heapq.heappush(priority_queue, (new_distance, neighbor))

    return heuristic_table


def find_path_timed(
    graph: Graph,
    start: str,
    goal: str,
    constraints: Constraints,
    start_turn: int,
    horizon: int,
    dist: Heuristic,
) -> TimedRoute | None:
    """Time-expanded A* returning the earliest feasible arrival route.

    State = (zone, turn); start = (start, start_turn); goal = any (goal, t).
    Successors: wait -> (z, t+1), move -> (w, t+enter_cost(w)).
    Vertex/link constraints prune states and transit moves. Heuristic
    f = turn + dist[zone]; priority zones break f-ties. Returns None if
    no route exists within ``horizon``.
    """
    if graph.zones[goal].zone_type == ZoneType.BLOCKED:
        return None

    if start == goal:
        return [(start, start_turn)]

    vertex_constraints, link_constraints = constraints

    start_state = (start, start_turn)
    initial_priority = (
        1 if graph.zones[start].zone_type == ZoneType.PRIORITY else 0
    )
    initial_f = start_turn + dist[start]
    priority_queue: list[_TimedQueueEntry] = [
        (initial_f, -initial_priority, start_turn, start)
    ]
    breadcrumbs: Breadcrumbs = {start_state: None}
    priority_count: PriorityCount = {start_state: initial_priority}
    best_g: BestG = {start_state: start_turn}

    while priority_queue:
        _f, _neg_priority, turn, zone_name = heapq.heappop(priority_queue)
        state = (zone_name, turn)

        if turn > best_g.get(state, turn):
            continue

        if zone_name == goal:
            return _reconstruct_path(breadcrumbs, state)

        wait_turn = turn + 1
        if wait_turn <= horizon:
            wait_state = (zone_name, wait_turn)
            if not _vertex_blocked(wait_state, vertex_constraints):
                _push_state(
                    priority_queue, breadcrumbs, priority_count, best_g,
                    dist, wait_state, state, priority_count[state],
                )

        for neighbor_name in graph.neighbors(zone_name):
            neighbor_zone = graph.zones[neighbor_name]

            if neighbor_zone.zone_type == ZoneType.BLOCKED:
                continue

            cost = _enter_cost(neighbor_zone)
            assert isinstance(cost, int), (
                "Cost should be int for non-blocked zones"
            )
            arrive_turn = turn + cost

            if arrive_turn > horizon:
                continue

            move_state = (neighbor_name, arrive_turn)

            if _vertex_blocked(move_state, vertex_constraints):
                continue

            link_key = canonical_key(zone_name, neighbor_name)
            if _is_link_blocked(link_key, turn, arrive_turn, link_constraints):
                continue

            new_priority = priority_count[state] + (
                1 if neighbor_zone.zone_type == ZoneType.PRIORITY else 0
            )

            _push_state(
                priority_queue, breadcrumbs, priority_count, best_g,
                dist, move_state, state, new_priority,
            )

    return None


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

    priority_queue: list[tuple[int | float, int, str]] = [(0, 0, start)]
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
