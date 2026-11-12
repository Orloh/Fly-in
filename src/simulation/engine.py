"""Turn-by-turn drone fleet simulation engine.

``Simulation`` computes a ``Schedule`` once via the greedy ``Planner`` at
construction, then ``step()`` replays it as a cursor. Transit countdown
happens at the end of each turn, so the returned ``TurnSnapshot`` reflects
the true internal positions after all moves have completed.
"""

from __future__ import annotations

from typing import Protocol, TypeAlias

from src.models import (
    ConnectionKey,
    Drone,
    DroneId,
    DronePosition,
    DronePositions,
    DroneStatus,
    Graph,
    LinkUsage,
    Movement,
    SimulationState,
    TurnEvent,
    TurnSnapshot,
    ZoneName,
    ZoneOccupancy,
)
from src.models.schedule import Schedule, ScheduledAction
from src.models.graph_utils import canonical_key
from src.simulation.planner import Planner

#: A human-readable capacity or routing failure reported on a turn.
Conflict: TypeAlias = str
#: Drone id to the connection it was on before a step.
TransitStart = dict[DroneId, ConnectionKey]


class PlannerProtocol(Protocol):
    """Structural type for any planner the engine can replay."""

    def plan(self, drones: list[Drone]) -> tuple[Schedule, list[Drone]]:
        """Compute a Schedule; return (schedule, blocked drones)."""
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
            self.schedule.occupancy()
        )
        self.state = SimulationState(drones={d.id: d for d in drones})
        self._blocked_reported: set[DroneId] = set()

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

    def step(self) -> TurnSnapshot:
        """Advance one turn and return its true end-of-turn snapshot."""
        self.state.turn += 1
        movements: list[Movement] = []
        conflicts: list[Conflict] = []
        in_transit_before: TransitStart = {
            drone.id: (drone.transit_from, drone.transit_destination)
            for drone in self.state.drones.values()
            if drone.status == DroneStatus.IN_TRANSIT
            and drone.transit_from is not None
            and drone.transit_destination is not None
        }

        # Replay the schedule in drone-id order.
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

        # Complete one transit step for every in-flight drone.
        for drone in self.state.drones.values():
            if drone.status != DroneStatus.IN_TRANSIT:
                continue
            drone.turns_remaining -= 1
            if drone.turns_remaining <= 0:
                self._arrive(drone)

        # First step: report drones blocked by the planner (no route).
        if self.state.turn == 1:
            for drone in self.state.drones.values():
                if drone.id in self._blocked_reported:
                    continue
                if drone.status == DroneStatus.BLOCKED:
                    conflicts.append(
                        f"drone {drone.id}: no route to {drone.target_zone}"
                    )
                    self._blocked_reported.add(drone.id)

        events = self._build_events(movements, in_transit_before)
        positions: DronePositions = {
            drone.id: self._position(drone)
            for drone in self.state.drones.values()
        }
        zone_occupancy: ZoneOccupancy = {}
        link_usage: LinkUsage = {}
        for position in positions.values():
            if position.zone is not None:
                zone_occupancy[position.zone] = (
                    zone_occupancy.get(position.zone, 0) + 1
                )
            if position.connection is not None:
                key = canonical_key(*position.connection)
                link_usage[key] = link_usage.get(key, 0) + 1

        zone_names: set[ZoneName] = {
            event.label for event in events if event.kind == "zone"
        }
        zone_capacities = {
            zone_name: self.graph.zones[zone_name].capacity
            for zone_name in zone_names
        }
        link_capacities = {
            key: self.graph.connections[key].max_link_capacity
            for key in link_usage
            if key in self.graph.connections
        }

        return TurnSnapshot(
            turn_number=self.state.turn,
            movements=movements,
            events=events,
            positions=positions,
            zone_occupancy=zone_occupancy,
            link_usage=link_usage,
            conflicts=conflicts,
            zone_capacities=zone_capacities,
            link_capacities=link_capacities,
        )

    def _build_events(
        self,
        movements: list[Movement],
        in_transit_before: TransitStart,
    ) -> list[TurnEvent]:
        """Build the tokens to print for this turn."""
        movement_ids = {movement.drone_id for movement in movements}
        events: list[TurnEvent] = []

        for movement in movements:
            if movement.turns_required == 1:
                events.append(
                    TurnEvent(
                        drone_id=movement.drone_id,
                        kind="zone",
                        label=movement.to_zone,
                    )
                )
            else:
                events.append(
                    TurnEvent(
                        drone_id=movement.drone_id,
                        kind="connection",
                        label=(
                            f"{movement.from_zone}-"
                            f"{movement.to_zone}"
                        ),
                    )
                )

        for drone_id in in_transit_before:
            if drone_id in movement_ids:
                continue
            drone = self.state.drones[drone_id]
            if (
                drone.status == DroneStatus.IN_TRANSIT
                and drone.transit_from is not None
                and drone.transit_destination is not None
            ):
                events.append(
                    TurnEvent(
                        drone_id=drone_id,
                        kind="connection",
                        label=(
                            f"{drone.transit_from}-"
                            f"{drone.transit_destination}"
                        ),
                    )
                )
            elif drone.current_zone is not None:
                events.append(
                    TurnEvent(
                        drone_id=drone_id,
                        kind="zone",
                        label=drone.current_zone,
                    )
                )

        events.sort(key=lambda event: event.drone_id)
        return events

    @staticmethod
    def _position(drone: Drone) -> DronePosition:
        """Return a drone's true position after the turn."""
        if drone.status == DroneStatus.IN_TRANSIT:
            if (
                drone.transit_from is not None
                and drone.transit_destination is not None
            ):
                return DronePosition(
                    connection=(
                        drone.transit_from,
                        drone.transit_destination,
                    ),
                    status=DroneStatus.IN_TRANSIT,
                )
        return DronePosition(
            zone=drone.current_zone,
            status=drone.status,
        )

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

        from_zone = drone.current_zone
        next_zone_name = action.to_zone

        drone.status = DroneStatus.IN_TRANSIT
        drone.current_zone = None
        drone.transit_from = from_zone
        drone.transit_destination = next_zone_name
        drone.turns_remaining = action.turns_required

        return Movement(
            drone_id=drone.id,
            from_zone=from_zone,
            to_zone=next_zone_name,
            turns_required=action.turns_required,
        )

    def _arrive(self, drone: Drone) -> None:
        """Land the drone at its destination."""
        if (
            drone.transit_from is None
            or drone.transit_destination is None
        ):
            return

        drone.current_zone = drone.transit_destination
        drone.transit_from = None
        drone.transit_destination = None
        drone.turns_remaining = 0

        if drone.current_zone == drone.target_zone:
            drone.status = DroneStatus.ARRIVED
            self.state.completed_drones.add(drone.id)
        else:
            drone.status = DroneStatus.WAITING
