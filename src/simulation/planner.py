"""Conflict-Based Search high-level planner.

``Planner`` computes a makespan-optimal ``Schedule`` for a drone fleet
using Conflict-Based Search: a constraint tree over capacity conflicts,
solved by repeated low-level ``find_path_timed`` calls. The schedule is
computed once, offline, and replayed by the engine.
"""

from __future__ import annotations

import heapq
from typing import NamedTuple, TypeAlias

from src.models import Drone, DroneStatus, Graph, canonical_key
from src.models.schedule import Schedule, ScheduledAction
from src.simulation.pathfinding import (
    Constraints,
    Heuristic,
    TimedRoute,
    dist_to_goal,
    find_path_timed,
    sum_entry_cost,
)

#: Per-drone constraint sets, keyed by drone id.
ConstraintsByDrone: TypeAlias = dict[int, Constraints]

#: Max constraint-tree expansions before degrading to the root schedule.
_CAP = 50_000


class SearchNode(NamedTuple):
    """A constraint-tree node: routes, constraints, and cost summary."""

    routes: dict[int, TimedRoute]
    constraints: ConstraintsByDrone
    makespan: int
    sum_arrivals: int
    n_constraints: int


class Planner:
    """Optimal-makespan fleet planner via Conflict-Based Search."""

    def __init__(self, graph: Graph) -> None:
        """Store the graph and prepare a heuristic cache."""
        self.graph = graph
        self._dist_cache: dict[str, Heuristic] = {}
        self._horizon = 1
        self._drones_by_id: dict[int, Drone] = {}

    def plan(self, drones: list[Drone]) -> tuple[Schedule, list[Drone]]:
        """Compute an optimal Schedule; return (schedule, blocked drones).

        Drones with no spatial route are marked BLOCKED with a
        ``blocked_reason`` and excluded from the search.
        """
        self._drones_by_id = {d.id: d for d in drones}
        self._horizon = 1 + len(drones) * sum_entry_cost(self.graph)

        blocked: list[Drone] = []
        root_routes: dict[int, TimedRoute] = {}
        root_constraints: ConstraintsByDrone = {}

        for drone in sorted(drones, key=lambda d: d.id):
            route = self._plan_drone(drone)
            if route is None:
                self._mark_blocked(drone)
                blocked.append(drone)
            else:
                root_routes[drone.id] = route
                root_constraints[drone.id] = (set(), set())

        if not root_routes:
            return Schedule(
                actions={}, makespan=0, graph=self.graph
            ), blocked

        root = SearchNode(
            routes=root_routes,
            constraints=root_constraints,
            makespan=_makespan(root_routes),
            sum_arrivals=_sum_arrivals(root_routes),
            n_constraints=0,
        )

        heap: list[tuple[int, int, int, int, SearchNode]] = [
            (root.makespan, root.sum_arrivals, root.n_constraints, 0, root)
        ]
        seen: set[tuple[tuple[tuple[str, int], ...], ...]] = {
            _route_signature(root_routes)
        }
        seq = 1
        expanded = 0

        while heap:
            _m, _s, _n, _seq, node = heapq.heappop(heap)
            expanded += 1
            if expanded > _CAP:
                return self._routes_to_schedule(root.routes), blocked

            conflict = self._first_conflict(node.routes)
            if conflict is None:
                return self._routes_to_schedule(node.routes), blocked

            for child in self._branch(node, conflict):
                signature = _route_signature(child.routes)
                if signature in seen:
                    continue
                seen.add(signature)
                heapq.heappush(
                    heap,
                    (child.makespan, child.sum_arrivals,
                     child.n_constraints, seq, child),
                )
                seq += 1

        return self._routes_to_schedule(root.routes), blocked

    def _plan_drone(self, drone: Drone) -> TimedRoute | None:
        """Find the drone's unconstrained route, or None if unreachable."""
        if drone.current_zone is None:
            return None
        goal = drone.target_zone
        if goal not in self.graph.zones or (
            drone.current_zone not in self.graph.zones
        ):
            return None
        dist = self._dist_cache.setdefault(
            goal, dist_to_goal(self.graph, goal)
        )
        return find_path_timed(
            self.graph,
            drone.current_zone,
            goal,
            (set(), set()),
            1,
            self._horizon,
            dist,
        )

    def _mark_blocked(self, drone: Drone) -> None:
        """Flag the drone as blocked with a reason."""
        drone.status = DroneStatus.BLOCKED
        drone.blocked_reason = "no route"

    def _build_occupancy(
        self,
        routes: dict[int, TimedRoute],
        horizon: int,
    ) -> tuple[
        dict[tuple[str, int], list[int]],
        dict[tuple[tuple[str, str], int], list[int]],
    ]:
        """Drone ids present at each (zone, turn) and (link, turn).

        Includes post-arrival tails: an arrived drone occupies its goal
        for every turn after arrival (D8).
        """
        zone_drones: dict[tuple[str, int], list[int]] = {}
        link_drones: dict[tuple[tuple[str, str], int], list[int]] = {}

        for drone_id, route in routes.items():
            for (a, ta), (b, tb) in zip(route, route[1:]):
                if a == b:
                    zone_drones.setdefault((a, ta), []).append(drone_id)
                else:
                    link = canonical_key(a, b)
                    for t in range(ta, tb):
                        link_drones.setdefault((link, t), []).append(drone_id)
                    zone_drones.setdefault((b, tb), []).append(drone_id)

            goal = route[-1][0]
            arrival = route[-1][1]
            for t in range(arrival + 1, horizon + 1):
                zone_drones.setdefault((goal, t), []).append(drone_id)

        return zone_drones, link_drones

    def _first_conflict(
        self, routes: dict[int, TimedRoute]
    ) -> tuple[str, tuple[str, str] | str, int, int, int] | None:
        """Return (kind, cell, turn, offender_a, offender_b) or None.

        Picks the conflict at the lowest (turn, canonical cell name) for
        determinism. ``cell`` is a zone name for zone conflicts and a
        canonical link tuple for link conflicts.
        """
        zone_drones, link_drones = self._build_occupancy(
            routes, self._horizon
        )
        conflicts: list[
            tuple[int, str, str, tuple[str, str] | str, list[int]]
        ] = []

        for (zone_name, turn), ids in zone_drones.items():
            zone = self.graph.zones.get(zone_name)
            if zone is None or zone.capacity is None:
                continue
            if len(ids) > zone.capacity:
                conflicts.append((turn, "zone", zone_name, zone_name, ids))

        for (link, turn), ids in link_drones.items():
            connection = self.graph.connections.get(link)
            if connection is None:
                continue
            if len(ids) > connection.max_link_capacity:
                conflicts.append((turn, "link", str(link), link, ids))

        if not conflicts:
            return None

        conflicts.sort(key=lambda c: (c[0], c[1], c[2]))
        turn, kind, _sort_key, cell, ids = conflicts[0]
        ids.sort()
        offender_a, offender_b = ids[0], ids[1]
        return kind, cell, turn, offender_a, offender_b

    def _branch(
        self,
        node: SearchNode,
        conflict: tuple[str, tuple[str, str] | str, int, int, int],
    ) -> list[SearchNode]:
        """Create two children forbidding one offender each at the cell."""
        kind, cell, turn, offender_a, offender_b = conflict
        children: list[SearchNode] = []

        for offender in (offender_a, offender_b):
            new_constraints = {
                drone_id: (set(vc), set(lc))
                for drone_id, (vc, lc) in node.constraints.items()
            }
            vc, lc = new_constraints[offender]
            if kind == "zone":
                assert isinstance(cell, str)
                vc.add((cell, turn))
            else:
                assert isinstance(cell, tuple)
                lc.add((cell, turn))
            new_constraints[offender] = (vc, lc)

            route = self._replan(offender, node.routes, new_constraints)
            if route is None:
                continue

            new_routes = dict(node.routes)
            new_routes[offender] = route
            children.append(
                SearchNode(
                    routes=new_routes,
                    constraints=new_constraints,
                    makespan=_makespan(new_routes),
                    sum_arrivals=_sum_arrivals(new_routes),
                    n_constraints=node.n_constraints + 1,
                )
            )

        return children

    def _replan(
        self,
        drone_id: int,
        routes: dict[int, TimedRoute],
        constraints: ConstraintsByDrone,
    ) -> TimedRoute | None:
        """Replan one drone under its new constraints, or None if pruned."""
        drone = self._drones_by_id[drone_id]
        assert drone.current_zone is not None
        goal = drone.target_zone
        dist = self._dist_cache[goal]
        return find_path_timed(
            self.graph,
            drone.current_zone,
            goal,
            constraints[drone_id],
            1,
            self._horizon,
            dist,
        )

    def _routes_to_schedule(
        self, routes: dict[int, TimedRoute]
    ) -> Schedule:
        """Convert per-drone TimedRoutes into a dense Schedule."""
        actions: dict[int, list[ScheduledAction]] = {}
        for drone_id, route in routes.items():
            actions[drone_id] = _route_to_actions(route)
        return Schedule(
            actions=actions,
            makespan=_makespan(routes),
            graph=self.graph,
        )


def _route_to_actions(route: TimedRoute) -> list[ScheduledAction]:
    """Convert a timed route into dense per-turn actions.

    Consecutive pairs (z1,t1)->(z2,t2): z1==z2 → WAIT at t1; z1!=z2 →
    MOVE(t1, from=z1, to=z2, turns_required=t2-t1).
    """
    actions: list[ScheduledAction] = []
    for (from_zone, t1), (to_zone, t2) in zip(route, route[1:]):
        if from_zone == to_zone:
            actions.append(
                ScheduledAction(
                    kind="WAIT",
                    turn=t1,
                    from_zone=from_zone,
                    to_zone=from_zone,
                    turns_required=1,
                )
            )
        else:
            actions.append(
                ScheduledAction(
                    kind="MOVE",
                    turn=t1,
                    from_zone=from_zone,
                    to_zone=to_zone,
                    turns_required=t2 - t1,
                )
            )
    return actions


def _makespan(routes: dict[int, TimedRoute]) -> int:
    """The turn the last drone arrives (0 for an empty fleet)."""
    if not routes:
        return 0
    return max(route[-1][1] for route in routes.values())


def _sum_arrivals(routes: dict[int, TimedRoute]) -> int:
    """Sum of arrival turns across drones."""
    return sum(route[-1][1] for route in routes.values())


def _route_signature(
    routes: dict[int, TimedRoute],
) -> tuple[tuple[tuple[str, int], ...], ...]:
    """Hashable fingerprint of the route assignment.

    Sorted per-drone route tuples, so interchangeable drones that end up
    on the same route collapse to one signature (agent symmetry breaking).
    """
    return tuple(sorted(tuple(route) for route in routes.values()))
