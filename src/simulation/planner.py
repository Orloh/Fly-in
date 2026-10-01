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
    LinkConstraint,
    TimedRoute,
    VertexConstraint,
    dist_to_goal,
    find_path_timed,
    sum_entry_cost,
)

#: Per-drone constraint sets, keyed by drone id.
ConstraintsByDrone: TypeAlias = dict[int, Constraints]

#: Max constraint-tree expansions before degrading to the greedy plan.
_CAP = 50_000

#: Above this fleet size CBS is intractable; plan greedily up front.
_MAX_CBS_DRONES = 8


class SearchNode(NamedTuple):
    """A constraint-tree node: routes, constraints, and cost summary."""

    routes: dict[int, TimedRoute]
    constraints: ConstraintsByDrone
    makespan: int
    n_conflicts: int
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

        Homogeneous fleets (all drones share start/end) are routed by the
        quickest-flow ``FlowPlanner``; its schedule is validated for
        cost-consistency and used only if sound, otherwise CBS runs. Any
        other fleet runs CBS. Drones with no spatial route are marked
        BLOCKED with a ``blocked_reason`` and excluded from the search.
        """
        if self._is_homogeneous(drones):
            schedule, blocked = self._plan_flow(drones)
            if schedule is not None:
                return schedule, blocked
        return self._plan_cbs(drones)

    def _is_homogeneous(self, drones: list[Drone]) -> bool:
        """Whether every drone shares the same start and target zones."""
        if not drones:
            return False
        start = drones[0].current_zone
        goal = drones[0].target_zone
        return all(
            d.current_zone == start and d.target_zone == goal
            for d in drones
        )

    def _plan_flow(
        self, drones: list[Drone]
    ) -> tuple[Schedule | None, list[Drone]]:
        """Run the flow planner; return its schedule if cost-consistent."""
        from src.simulation.flow import FlowPlanner

        schedule, blocked = FlowPlanner(self.graph).plan(drones)
        if schedule.actions and not _cost_consistent(schedule, self.graph):
            return None, blocked
        return schedule, blocked

    def _plan_cbs(self, drones: list[Drone]) -> tuple[Schedule, list[Drone]]:
        """Run Conflict-Based Search (with greedy fallbacks)."""
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

        # Large fleets exceed the CBS design scale: plan greedily up front
        # (each drone avoids already-committed occupancy) so the run is
        # valid and fast instead of exhausting the expansion cap.
        if len(drones) > _MAX_CBS_DRONES:
            return self._greedy_fallback(drones), blocked

        if not root_routes:
            return Schedule(
                actions={}, makespan=0, graph=self.graph
            ), blocked

        root = SearchNode(
            routes=root_routes,
            constraints=root_constraints,
            makespan=_makespan(root_routes),
            n_conflicts=self._count_conflicts(root_routes),
            sum_arrivals=_sum_arrivals(root_routes),
            n_constraints=0,
        )

        heap: list[tuple[int, int, int, int, int, SearchNode]] = [
            (root.makespan, root.n_conflicts, root.sum_arrivals,
             root.n_constraints, 0, root)
        ]
        seen: set[tuple[tuple[tuple[str, int], ...], ...]] = {
            _route_signature(root_routes)
        }
        seq = 1
        expanded = 0

        while heap:
            _m, _c, _s, _n, _seq, node = heapq.heappop(heap)
            expanded += 1
            if expanded > _CAP:
                return self._greedy_fallback(drones), blocked

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
                    (child.makespan, child.n_conflicts,
                     child.sum_arrivals, child.n_constraints, seq, child),
                )
                seq += 1

        return self._greedy_fallback(drones), blocked

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

    def _greedy_fallback(
        self, drones: list[Drone]
    ) -> Schedule:
        """Return a valid (conflict-free) schedule via prioritized planning.

        Plans drones in id order; each drone is routed against the
        occupancy of already-committed drones via vertex/link constraints.
        Complete because the start hub is unlimited — a drone can always
        wait there. Used when the CBS expansion cap is hit (large fleets).
        """
        routes: dict[int, TimedRoute] = {}
        for drone in sorted(drones, key=lambda d: d.id):
            if drone.current_zone is None:
                continue
            goal = drone.target_zone
            if goal not in self.graph.zones or (
                drone.current_zone not in self.graph.zones
            ):
                continue
            dist = self._dist_cache.setdefault(
                goal, dist_to_goal(self.graph, goal)
            )
            route = find_path_timed(
                self.graph,
                drone.current_zone,
                goal,
                self._reservation_constraints(routes),
                1,
                self._horizon,
                dist,
            )
            if route is not None:
                routes[drone.id] = route
        return self._routes_to_schedule(routes)

    def _reservation_constraints(
        self, routes: dict[int, TimedRoute]
    ) -> Constraints:
        """Constraints forbidding cells already at capacity for new drones."""
        zone_drones, link_drones = self._build_occupancy(
            routes, self._horizon
        )
        vertex: set[VertexConstraint] = set()
        link: set[LinkConstraint] = set()
        for (zone_name, turn), ids in zone_drones.items():
            zone = self.graph.zones.get(zone_name)
            if zone is None or zone.capacity is None:
                continue
            if len(ids) >= zone.capacity:
                vertex.add((zone_name, turn))
        for (link_key, turn), ids in link_drones.items():
            connection = self.graph.connections.get(link_key)
            if connection is None:
                continue
            if len(ids) >= connection.max_link_capacity:
                link.add((link_key, turn))
        return vertex, link

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

    def _count_conflicts(self, routes: dict[int, TimedRoute]) -> int:
        """Number of zone/link cells over capacity across the routes."""
        zone_drones, link_drones = self._build_occupancy(
            routes, self._horizon
        )
        count = 0
        for (zone_name, turn), ids in zone_drones.items():
            zone = self.graph.zones.get(zone_name)
            if zone is not None and zone.capacity is not None:
                if len(ids) > zone.capacity:
                    count += 1
        for (link, turn), ids in link_drones.items():
            connection = self.graph.connections.get(link)
            if connection is not None:
                if len(ids) > connection.max_link_capacity:
                    count += 1
        return count

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
                    n_conflicts=self._count_conflicts(new_routes),
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
        routes = self._assign_routes(routes)
        actions: dict[int, list[ScheduledAction]] = {}
        for drone_id, route in routes.items():
            actions[drone_id] = _route_to_actions(route)
        return Schedule(
            actions=actions,
            makespan=_makespan(routes),
            graph=self.graph,
        )

    def _assign_routes(
        self, routes: dict[int, TimedRoute]
    ) -> dict[int, TimedRoute]:
        """Deterministically assign routes to interchangeable drones.

        Drones sharing the same (start, goal) are interchangeable, so
        their routes are sorted by arrival turn and handed to drone ids
        in ascending order. Keeps the output stable despite the
        agent-symmetry route dedup in the search.
        """
        assigned: dict[int, TimedRoute] = {}
        trips: dict[tuple[str | None, str], list[int]] = {}
        for drone_id in sorted(routes):
            drone = self._drones_by_id[drone_id]
            key = (drone.current_zone, drone.target_zone)
            trips.setdefault(key, []).append(drone_id)

        for drone_ids in trips.values():
            ordered = sorted(
                drone_ids, key=lambda did: (routes[did][-1][1], routes[did])
            )
            for drone_id, route in zip(drone_ids, ordered):
                assigned[drone_id] = routes[route]
        return assigned


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


def _cost_consistent(schedule: Schedule, graph: Graph) -> bool:
    """Whether every MOVE's transit length matches the destination cost.

    The shared flow link chain can "splice" a drone past a restricted
    zone in 1 turn; such a schedule is physically invalid and must not
    be returned. Validates each MOVE's ``turns_required`` against the
    destination zone's entry cost.

    This is the designed gate that keeps flow sound: flow is trusted
    only on splice-free (all-normal) maps, and restricted maps defer to
    CBS. The splice cannot be removed from the network itself because
    occupancy-based link capacity with transit > 1 is inexpressible in
    anonymous single-commodity flow (see ``flow.py`` module docstring).
    """
    from src.simulation.pathfinding import _enter_cost

    for drone_actions in schedule.actions.values():
        for action in drone_actions:
            if action.kind != "MOVE":
                continue
            dest = graph.zones.get(action.to_zone)
            if dest is None:
                return False
            cost = _enter_cost(dest)
            if not isinstance(cost, int) or action.turns_required != cost:
                return False
    return True


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
