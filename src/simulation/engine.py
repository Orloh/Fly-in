"""Turn-by-turn drone fleet simulation engine.

``Simulation`` drives a fleet through a ``Graph`` one turn at a time.
Waiting drones plan a route with ``find_path`` and start hops; in-flight
drones count down their traversal turns; failures (no route, zone at
capacity, link at capacity) surface as conflicts on each ``TurnResult``.
"""

from __future__ import annotations

from typing import TypeAlias

from src.models import (
    Drone,
    DroneStatus,
    Graph,
    Movement,
    SimulationState,
    TurnResult,
    Zone,
)
from src.simulation.pathfinding import _enter_cost, find_path

#: A human-readable capacity or routing failure reported on a turn.
Conflict: TypeAlias = str

#: Link key uses traversal direction (from_zone, to_zone) for link_usage.
LinkKey: TypeAlias = tuple[str, str]


class Simulation:
    """Turn-by-turn executor over a graph and a drone fleet."""

    def __init__(self, graph: Graph, drones: list[Drone]) -> None:
        """Store the graph and build the initial SimulationState."""
        self.graph = graph
        drone_dict = {d.id: d for d in drones}
        self.state = SimulationState(drones=drone_dict)
        # Reservations for destination zones: zone_name -> count
        self._zone_reservations: dict[str, int] = {}
        # Departing drones this turn: zone_name -> count
        self._departing: dict[str, int] = {}

    @property
    def finished(self) -> bool:
        """Whether every drone has arrived at its target zone."""
        if not self.state.drones:
            return True
        return all(
            d.status == DroneStatus.ARRIVED
            for d in self.state.drones.values()
        )

    def step(self) -> TurnResult:
        """Advance one turn and return its movements and conflicts."""
        self.state.turn += 1
        movements: list[Movement] = []
        conflicts: list[Conflict] = []

        # Reset per-turn tracking
        self._zone_reservations.clear()
        self._departing.clear()

        # Process in-transit drones (arrivals)
        for drone in self.state.drones.values():
            if drone.status == DroneStatus.IN_TRANSIT:
                drone.turns_in_transit -= 1
                if drone.turns_in_transit <= 0:
                    self._arrive(drone)

        self.state.update_occupancy()

        # Track handled drones to avoid duplicate conflicts
        handled_drones: set[int] = set()

        # Keep processing waiting drones until no moves
        while True:
            # Get all currently waiting drones not yet handled
            waiting_drones = sorted(
                [
                    d
                    for d in self.state.drones.values()
                    if d.status == DroneStatus.WAITING
                    and d.id not in handled_drones
                ],
                key=lambda d: d.id,
            )

            if not waiting_drones:
                break

            # Pre-compute paths and intended next hops for all waiting drones
            intended_moves: dict[int, str] = {}  # drone_id -> next_zone_name
            for drone in waiting_drones:
                self._ensure_path(drone)
                if drone.status == DroneStatus.BLOCKED:
                    handled_drones.add(drone.id)
                    conflicts.append(
                        f"drone {drone.id}: no route to {drone.target_zone}"
                    )
                elif drone.path:
                    intended_moves[drone.id] = drone.path[0]

            # Compute departures: count drones intending to leave each zone
            self._departing.clear()
            for drone in self.state.drones.values():
                if (
                    drone.status == DroneStatus.WAITING
                    and drone.id in intended_moves
                ):
                    if drone.current_zone is not None:
                        self._departing[drone.current_zone] = (
                            self._departing.get(drone.current_zone, 0) + 1
                        )

            # Process moves in id order
            moved_any = False
            for drone in waiting_drones:
                if drone.id not in intended_moves:
                    continue  # blocked or no path

                next_zone_name = intended_moves[drone.id]
                next_zone = self.graph.zones[next_zone_name]

                conflict = self._capacity_conflict(drone, next_zone)
                if conflict:
                    conflicts.append(conflict)
                    handled_drones.add(drone.id)
                else:
                    movement = self._start_hop(drone)
                    if movement:
                        movements.append(movement)
                        moved_any = True
                        handled_drones.add(drone.id)
                        self.state.update_occupancy()

            if not moved_any:
                # No drone could move; remaining waiting drones are blocked
                for drone in waiting_drones:
                    if (
                        drone.id not in handled_drones
                        and drone.status == DroneStatus.WAITING
                    ):
                        if drone.path:
                            next_zone_name = drone.path[0]
                            next_zone = self.graph.zones[next_zone_name]
                            conflict = self._capacity_conflict(
                                drone, next_zone
                            )
                            if conflict:
                                conflicts.append(conflict)
                        handled_drones.add(drone.id)
                break

        return TurnResult(
            turn_number=self.state.turn,
            movements=movements,
            conflicts=conflicts,
        )

    def _ensure_path(self, drone: Drone) -> None:
        """Plan the drone's route, marking it BLOCKED if unreachable."""
        if drone.path or drone.current_zone == drone.target_zone:
            return

        if drone.current_zone is None:
            return

        route = find_path(self.graph, drone.current_zone, drone.target_zone)

        if route is None:
            drone.status = DroneStatus.BLOCKED
        else:
            drone.path = route[1:]

    def _capacity_conflict(
        self, drone: Drone, dest: Zone
    ) -> Conflict | None:
        """Return the conflict blocking a hop into ``dest``, or None."""
        if drone.current_zone is None:
            return None

        # Check zone capacity: load = physical + reserved - departing
        if dest.capacity is not None:
            physical = self.state.zone_occupancy.get(dest.name, 0)
            reserved = self._zone_reservations.get(dest.name, 0)
            departing = self._departing.get(dest.name, 0)
            load = physical + reserved - departing
            if load >= dest.capacity:
                return f"drone {drone.id} zone {dest.name} at capacity"

        # Check link capacity: undirected link, sum usage in both directions
        zone_a, zone_b = drone.current_zone, dest.name
        link_key = (zone_a, zone_b)  # traversal direction for storage
        canon_key = (zone_a, zone_b) if zone_a <= zone_b else (zone_b, zone_a)
        connection = self.graph.connections.get(canon_key)
        if connection is not None:
            # Total usage on this undirected link (both directions)
            rev_key = (zone_b, zone_a)
            total_usage = (
                self.state.link_usage.get(link_key, 0)
                + self.state.link_usage.get(rev_key, 0)
            )
            if total_usage >= connection.max_link_capacity:
                return f"drone {drone.id}: link {zone_a}-{zone_b} at capacity"

        return None

    def _start_hop(self, drone: Drone) -> Movement | None:
        """Commit the drone to its next hop, announcing a Movement."""
        if not drone.path or drone.current_zone is None:
            return None

        next_zone_name = drone.path.pop(0)
        next_zone = self.graph.zones[next_zone_name]

        zone_a, zone_b = drone.current_zone, next_zone_name
        link_key = (zone_a, zone_b)  # traversal direction

        drone.status = DroneStatus.IN_TRANSIT
        drone.transit_destination = next_zone_name
        drone.turns_in_transit = int(_enter_cost(next_zone))

        # Track link usage (traversal direction)
        self.state.link_usage[link_key] = (
            self.state.link_usage.get(link_key, 0) + 1
        )

        # Track reservations
        self._zone_reservations[next_zone_name] = (
            self._zone_reservations.get(next_zone_name, 0) + 1
        )

        return Movement(
            drone_id=drone.id,
            from_zone=drone.current_zone,
            to_zone=next_zone_name,
            turns_required=drone.turns_in_transit,
        )

    def _arrive(self, drone: Drone) -> None:
        """Land the drone at its destination and release its link."""
        if drone.current_zone is None or drone.transit_destination is None:
            return

        zone_a, zone_b = drone.current_zone, drone.transit_destination
        link_key = (zone_a, zone_b)  # traversal direction

        # Release link usage
        if link_key in self.state.link_usage:
            self.state.link_usage[link_key] = max(
                0, self.state.link_usage[link_key] - 1
            )

        # Release reservation on arrival zone (becomes physical
        # via update_occupancy)
        if zone_b in self._zone_reservations:
            self._zone_reservations[zone_b] = max(
                0, self._zone_reservations[zone_b] - 1
            )

        drone.current_zone = drone.transit_destination
        drone.transit_destination = None

        if drone.current_zone == drone.target_zone:
            drone.status = DroneStatus.ARRIVED
            self.state.completed_drones.add(drone.id)
        else:
            drone.status = DroneStatus.WAITING
