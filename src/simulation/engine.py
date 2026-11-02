"""Turn-by-turn drone fleet simulation engine.

``Simulation`` computes a ``Schedule`` once via the greedy
``Planner`` at construction, then ``step()`` replays it as a cursor.
Waiting drones look up their scheduled action for the current turn:
MOVE starts a hop, WAIT stays silently. Planned waits are silent; the
only conflicts are no-route (BLOCKED drones, first step) and safety-net
violations (planner bugs, visible with --debug).
"""

from __future__ import annotations

from typing import Protocol, TypeAlias

from src.models import (
    Drone,
    DroneStatus,
    Graph,
    Movement,
    SimulationState,
    TurnResult,
)
from src.models.schedule import Schedule, ScheduledAction
from src.models.graph_utils import canonical_key
from src.simulation.planner import Planner

#: A human-readable capacity or routing failure reported on a turn.
Conflict: TypeAlias = str


class PlannerProtocol(Protocol):
    """Structural type for any planner the engine can replay."""

    def plan(self, drones: list[Drone]) -> tuple[Schedule, list[Drone]]:
        """Compute an optimal Schedule; return (schedule, blocked drones)."""
        ...


class Simulation:
    """Turn-by-turn executor over a graph and a drone fleet."""

    def __init__(
        self,
        graph: Graph,
        drones: list[Drone],
        planner: PlannerProtocol | None = None,
    ) -> None:
        """Plan a Schedule and prepare the replay state.

        Args:
            graph: The routing graph.
            drones: The fleet to simulate.
            planner: The planner to use; defaults to ``Planner``.
        """
        self.graph = graph
        planner = planner or Planner(graph)
        schedule, _blocked = planner.plan(drones)
        for drone in drones:
            drone.schedule = schedule.actions.get(drone.id, [])
            drone.schedule_index = 0
        self.schedule = schedule
        self._schedule_zone_time, self._schedule_link_time = (
            self.schedule._occupancy()
        )
        self.state = SimulationState(drones={d.id: d for d in drones})
        self._blocked_reported: set[int] = set()

    @property
    def finished(self) -> bool:
        """Whether every drone has arrived at its target zone.

        Returns:
            True when all drones have arrived, or the fleet is empty.
        """
        if not self.state.drones:
            return True
        return all(
            d.status == DroneStatus.ARRIVED
            for d in self.state.drones.values()
        )

    def step(self) -> TurnResult:
        """Advance one turn and return its movements and conflicts.

        Returns:
            The movements and conflicts reported on this turn.
        """
        self.state.turn += 1
        movements: list[Movement] = []
        conflicts: list[Conflict] = []

        # Process in-transit drones (arrivals)
        for drone in self.state.drones.values():
            if drone.status == DroneStatus.IN_TRANSIT:
                drone.turns_in_transit -= 1
                if drone.turns_in_transit <= 0:
                    self._arrive(drone)

        start_occupancy = self._zone_counts()

        # Replay the schedule in drone-id order
        for drone in sorted(
            self.state.drones.values(), key=lambda d: d.id
        ):
            if drone.status != DroneStatus.WAITING:
                continue
            if drone.schedule_index >= len(drone.schedule):
                continue
            action = drone.schedule[drone.schedule_index]
            if action.turn > self.state.turn:
                continue

            if action.kind == "WAIT":
                drone.schedule_index += 1
                continue

            conflict = self._capacity_conflict(drone, action)
            if conflict:
                conflicts.append(conflict)
                continue

            movement = self._start_hop(drone, action)
            if movement:
                movements.append(movement)
                drone.schedule_index += 1

        # First step: report drones blocked by the planner (no route)
        if self.state.turn == 1:
            for drone in self.state.drones.values():
                if drone.id in self._blocked_reported:
                    continue
                if drone.status == DroneStatus.BLOCKED:
                    conflicts.append(
                        f"drone {drone.id}: no route to {drone.target_zone}"
                    )
                    self._blocked_reported.add(drone.id)

        moved_zones = self._moved_zones(movements)
        capacities = {
            zone_name: self.graph.zones[zone_name].capacity
            for zone_name in moved_zones
        }
        return TurnResult(
            turn_number=self.state.turn,
            movements=movements,
            conflicts=conflicts,
            zone_occupancy=self._occupancy_after_moves(
                start_occupancy, movements
            ),
            moved_zones=moved_zones,
            capacities=capacities,
        )

    def _moved_zones(self, movements: list[Movement]) -> set[str]:
        """Return zones displayed as zone tokens on this turn."""
        moved_ids = {movement.drone_id for movement in movements}
        zones = {
            movement.to_zone
            for movement in movements
            if movement.turns_required == 1
        }

        for drone in self.state.drones.values():
            if (
                drone.id not in moved_ids
                and drone.status == DroneStatus.IN_TRANSIT
                and drone.turns_in_transit <= 1
                and drone.transit_destination is not None
            ):
                zones.add(drone.transit_destination)
        return zones

    def _zone_counts(self) -> dict[str, int]:
        """Count drones occupying zones after arrivals, before moves."""
        counts: dict[str, int] = {}
        for drone in self.state.drones.values():
            if drone.status == DroneStatus.IN_TRANSIT:
                continue
            if drone.current_zone is None:
                continue
            counts[drone.current_zone] = (
                counts.get(drone.current_zone, 0) + 1
            )
        return counts

    def _occupancy_after_moves(
        self,
        start_occupancy: dict[str, int],
        movements: list[Movement],
    ) -> dict[str, int]:
        """Project zone occupancy at the end of the current turn.

        Normal moves arrive by the end of the turn. Restricted moves
        remain in flight unless this is their final transit turn.
        """
        counts = dict(start_occupancy)
        moved_ids = {movement.drone_id for movement in movements}

        for movement in movements:
            counts[movement.from_zone] = max(
                0, counts.get(movement.from_zone, 0) - 1
            )
            if movement.turns_required == 1:
                counts[movement.to_zone] = (
                    counts.get(movement.to_zone, 0) + 1
                )

        for drone in self.state.drones.values():
            if (
                drone.id not in moved_ids
                and drone.status == DroneStatus.IN_TRANSIT
                and drone.turns_in_transit <= 1
                and drone.transit_destination is not None
            ):
                destination = drone.transit_destination
                counts[destination] = counts.get(destination, 0) + 1

        return {
            zone_name: count
            for zone_name, count in counts.items()
            if count > 0
        }

    def _capacity_conflict(
        self,
        drone: Drone,
        action: ScheduledAction,
    ) -> Conflict | None:
        """Return the conflict blocking ``action``, or None.

        Checks the schedule's own occupancy model (the planner's
        conflict-free proof). A valid schedule never fires; a planner bug
        that exceeds capacity surfaces here.
        """
        if drone.current_zone is None:
            return None

        arrival = action.turn + action.turns_required

        dest = self.graph.zones[action.to_zone]
        if dest.capacity is not None:
            count = self._schedule_zone_time.get(
                (action.to_zone, arrival), 0
            )
            if count > dest.capacity:
                return f"drone {drone.id} zone {action.to_zone} at capacity"

        link_key = canonical_key(action.from_zone, action.to_zone)
        connection = self.graph.connections.get(link_key)
        if connection is not None:
            for t in range(action.turn, arrival):
                count = self._schedule_link_time.get((link_key, t), 0)
                if count > connection.max_link_capacity:
                    return (
                        f"drone {drone.id}: link "
                        f"{action.from_zone}-{action.to_zone} at capacity"
                    )

        return None

    def _start_hop(
        self, drone: Drone, action: ScheduledAction
    ) -> Movement | None:
        """Commit the drone to the hop described by ``action``."""
        if drone.current_zone is None:
            return None

        next_zone_name = action.to_zone
        link_key = (drone.current_zone, next_zone_name)

        drone.status = DroneStatus.IN_TRANSIT
        drone.transit_destination = next_zone_name
        drone.turns_in_transit = action.turns_required

        # Track link usage (traversal direction)
        self.state.link_usage[link_key] = (
            self.state.link_usage.get(link_key, 0) + 1
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
        link_key = (zone_a, zone_b)

        # Release link usage
        if link_key in self.state.link_usage:
            self.state.link_usage[link_key] = max(
                0, self.state.link_usage[link_key] - 1
            )

        drone.current_zone = drone.transit_destination
        drone.transit_destination = None
        drone.turns_in_transit = 0

        if drone.current_zone == drone.target_zone:
            drone.status = DroneStatus.ARRIVED
            self.state.completed_drones.add(drone.id)
        else:
            drone.status = DroneStatus.WAITING
