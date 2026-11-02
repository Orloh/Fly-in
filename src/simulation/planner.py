"""Greedy prioritized planner for the Fly-in simulation.

Drones are routed one at a time in ascending id order. Each drone uses
time-expanded A* while respecting the capacity reservations made by all
previously committed routes. The result is valid and deterministic, but
not guaranteed to minimize makespan.
"""

from __future__ import annotations

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


class Planner:
    """Route drones greedily in id order with capacity reservations."""

    def __init__(self, graph: Graph) -> None:
        """Store the graph and prepare a distance cache.

        Args:
            graph: The routing graph.
        """
        self.graph = graph
        self._dist_cache: dict[str, Heuristic] = {}

    def plan(self, drones: list[Drone]) -> tuple[Schedule, list[Drone]]:
        """Plan all drones greedily and return the schedule plus blocked ones.

        Args:
            drones: The fleet to route.

        Returns:
            The greedy schedule and the drones that could not be routed.
        """
        if not drones:
            return Schedule(
                actions={}, makespan=0, graph=self.graph
            ), []

        horizon = 1 + len(drones) * sum_entry_cost(self.graph)
        ordered = sorted(drones, key=lambda item: item.id)
        routes, blocked = self._plan_order(ordered, horizon)

        # A strict id order can serialize a head-on swap badly. If any
        # drone failed, retry with the reverse order and keep the better
        # result: fewer blocked drones first, then lower makespan.
        if blocked:
            alt_routes, alt_blocked = self._plan_order(
                list(reversed(ordered)), horizon
            )
            if (
                len(alt_blocked), _makespan(alt_routes)
            ) < (
                len(blocked), _makespan(routes)
            ):
                routes, blocked = alt_routes, alt_blocked

        for drone in blocked:
            self._mark_blocked(drone)
        return self._routes_to_schedule(routes), blocked

    def _plan_order(
        self,
        order: list[Drone],
        horizon: int,
    ) -> tuple[dict[int, TimedRoute], list[Drone]]:
        """Plan one prioritized pass in the given drone order."""
        routes: dict[int, TimedRoute] = {}
        blocked: list[Drone] = []
        for drone in order:
            route = self._plan_drone(drone, routes, horizon)
            if route is None:
                blocked.append(drone)
            else:
                routes[drone.id] = route
        return routes, blocked

    def _plan_drone(
        self,
        drone: Drone,
        committed: dict[int, TimedRoute],
        horizon: int,
    ) -> TimedRoute | None:
        """Plan one drone around already committed routes."""
        if drone.current_zone is None:
            return None
        if (
            drone.current_zone not in self.graph.zones
            or drone.target_zone not in self.graph.zones
        ):
            return None

        dist = self._dist_cache.setdefault(
            drone.target_zone,
            dist_to_goal(self.graph, drone.target_zone),
        )
        constraints = self._reservation_constraints(committed, horizon)
        return find_path_timed(
            self.graph,
            drone.current_zone,
            drone.target_zone,
            constraints,
            1,
            horizon,
            dist,
        )

    def _reservation_constraints(
        self,
        routes: dict[int, TimedRoute],
        horizon: int,
    ) -> Constraints:
        """Constraints forbidding cells already at capacity."""
        zone_drones, link_drones = self._build_occupancy(routes, horizon)
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
        """Map occupied zone/link cells to the drones currently using them.

        Arrrived drones keep occupying their goal after arrival.
        """
        zone_drones: dict[tuple[str, int], list[int]] = {}
        link_drones: dict[tuple[tuple[str, str], int], list[int]] = {}

        for drone_id, route in routes.items():
            for (zone_a, turn_a), (zone_b, turn_b) in zip(
                route, route[1:]
            ):
                if zone_a == zone_b:
                    zone_drones.setdefault(
                        (zone_a, turn_a), []
                    ).append(drone_id)
                else:
                    link = canonical_key(zone_a, zone_b)
                    for turn in range(turn_a, turn_b):
                        link_drones.setdefault(
                            (link, turn), []
                        ).append(drone_id)
                    zone_drones.setdefault(
                        (zone_b, turn_b), []
                    ).append(drone_id)

            goal = route[-1][0]
            arrival = route[-1][1]
            for turn in range(arrival + 1, horizon + 1):
                zone_drones.setdefault(
                    (goal, turn), []
                ).append(drone_id)

        return zone_drones, link_drones

    def _routes_to_schedule(
        self, routes: dict[int, TimedRoute]
    ) -> Schedule:
        """Convert committed timed routes into scheduled actions."""
        actions = {
            drone_id: _route_to_actions(route)
            for drone_id, route in routes.items()
        }
        return Schedule(
            actions=actions,
            makespan=_makespan(routes),
            graph=self.graph,
        )

    def _mark_blocked(self, drone: Drone) -> None:
        """Mark a drone that has no valid route."""
        drone.status = DroneStatus.BLOCKED
        drone.blocked_reason = "no route"


def _route_to_actions(route: TimedRoute) -> list[ScheduledAction]:
    """Convert a timed route into dense MOVE/WAIT actions."""
    actions: list[ScheduledAction] = []
    for (zone_a, turn_a), (zone_b, turn_b) in zip(route, route[1:]):
        if zone_a == zone_b:
            actions.append(
                ScheduledAction(
                    kind="WAIT",
                    turn=turn_a,
                    from_zone=zone_a,
                    to_zone=zone_a,
                    turns_required=1,
                )
            )
        else:
            actions.append(
                ScheduledAction(
                    kind="MOVE",
                    turn=turn_a,
                    from_zone=zone_a,
                    to_zone=zone_b,
                    turns_required=turn_b - turn_a,
                )
            )
    return actions


def _makespan(routes: dict[int, TimedRoute]) -> int:
    """Return the number of emitted turns until the last delivery."""
    if not routes:
        return 0
    return max(route[-1][1] - 1 for route in routes.values())
