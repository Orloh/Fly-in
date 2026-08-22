"""Tests for the turn-based drone fleet simulation engine (milestone).

``Simulation.step`` advances one turn: waiting drones move along their
paths, in-flight drones count down their traversal turns, and conflicts
(zone capacity, link capacity, unreachable goals) are reported.
"""

from __future__ import annotations

from src.models import (
    Connection,
    Drone,
    DroneStatus,
    Graph,
    Movement,
    Zone,
    ZoneType,
)
from src.simulation.engine import Simulation


def _zone(
    name: str,
    ztype: ZoneType = ZoneType.NORMAL,
    max_drones: int = 1,
    start: bool = False,
    end: bool = False,
) -> Zone:
    """Build a Zone with the given capacity, type, and hub flags."""
    return Zone(
        name=name,
        x=0,
        y=0,
        zone_type=ztype,
        max_drones=max_drones,
        is_start_hub=start,
        is_end_hub=end,
    )


def _drone(drone_id: int, current: str, target: str) -> Drone:
    """Build a drone starting at ``current`` heading to ``target``."""
    return Drone(id=drone_id, current_zone=current, target_zone=target)


def _graph(
    zones: list[Zone],
    edges: list[tuple[str, str]],
    link_capacity: int = 1,
) -> Graph:
    """Build a Graph with every edge sharing ``link_capacity``."""
    connections: dict[tuple[str, str], Connection] = {}
    for zone_a, zone_b in edges:
        key = (zone_a, zone_b) if zone_a <= zone_b else (zone_b, zone_a)
        connections[key] = Connection(
            zone_a=key[0],
            zone_b=key[1],
            max_link_capacity=link_capacity,
        )
    return Graph(
        zones={zone.name: zone for zone in zones},
        connections=connections,
    )


class TestSimulation:
    """Turn-by-turn movement, capacity, and conflict behaviour."""

    def test_single_drone_traverses_line_and_finishes(self) -> None:
        graph = _graph(
            [_zone("S", start=True), _zone("A"), _zone("G", end=True)],
            [("S", "A"), ("A", "G")],
        )
        sim = Simulation(graph, [_drone(1, "S", "G")])

        results = []
        while not sim.finished:
            results.append(sim.step())

        assert sim.state.turn == 3
        movements = [m for result in results for m in result.movements]
        assert movements == [
            Movement(
                drone_id=1, from_zone="S", to_zone="A", turns_required=1
            ),
            Movement(
                drone_id=1, from_zone="A", to_zone="G", turns_required=1
            ),
        ]
        assert sim.state.drones[1].status == DroneStatus.ARRIVED
        assert sim.state.drones[1].current_zone == "G"
        assert sim.state.completed_drones == {1}

    def test_restricted_zone_holds_link_for_two_turns(self) -> None:
        graph = _graph(
            [
                _zone("S", start=True),
                _zone("R", ZoneType.RESTRICTED),
                _zone("G", end=True),
            ],
            [("S", "R"), ("R", "G")],
        )
        sim = Simulation(graph, [_drone(1, "S", "G")])

        first = sim.step()
        assert first.movements == [
            Movement(
                drone_id=1, from_zone="S", to_zone="R", turns_required=2
            )
        ]
        assert sim.state.drones[1].status == DroneStatus.IN_TRANSIT
        assert sim.state.link_usage[("S", "R")] == 1

        second = sim.step()
        assert second.movements == []
        assert sim.state.drones[1].status == DroneStatus.IN_TRANSIT

        third = sim.step()
        assert third.movements == [
            Movement(
                drone_id=1, from_zone="R", to_zone="G", turns_required=1
            )
        ]

        sim.step()
        assert sim.finished
        assert sim.state.turn == 4

    def test_unreachable_goal_blocks_drone(self) -> None:
        graph = _graph(
            [
                _zone("S", start=True),
                _zone("G", end=True),
                _zone("B", ZoneType.BLOCKED),
            ],
            [("S", "B"), ("B", "G")],
        )
        sim = Simulation(graph, [_drone(1, "S", "G")])

        result = sim.step()

        assert result.movements == []
        assert len(result.conflicts) == 1
        assert "drone 1" in result.conflicts[0]
        assert "no route" in result.conflicts[0]
        assert sim.state.drones[1].status == DroneStatus.BLOCKED
        assert not sim.finished

    def test_zone_capacity_makes_second_drone_wait(self) -> None:
        graph = _graph(
            [
                _zone("S", start=True),
                _zone("A", max_drones=1),
                _zone("G", end=True),
            ],
            [("S", "A"), ("A", "G")],
        )
        sim = Simulation(graph, [_drone(1, "S", "G"), _drone(2, "S", "G")])

        first = sim.step()

        assert first.movements == [
            Movement(
                drone_id=1, from_zone="S", to_zone="A", turns_required=1
            )
        ]
        assert len(first.conflicts) == 1
        assert "drone 2" in first.conflicts[0]
        assert "capacity" in first.conflicts[0]
        assert sim.state.drones[2].status == DroneStatus.WAITING
        assert sim.state.drones[2].current_zone == "S"

    def test_zone_capacity_drone_proceeds_after_zone_frees(self) -> None:
        graph = _graph(
            [
                _zone("S", start=True),
                _zone("A", max_drones=1),
                _zone("G", end=True),
            ],
            [("S", "A"), ("A", "G")],
        )
        sim = Simulation(graph, [_drone(1, "S", "G"), _drone(2, "S", "G")])

        while not sim.finished:
            sim.step()

        assert sim.state.turn == 4
        assert sim.state.completed_drones == {1, 2}

    def test_link_capacity_makes_second_drone_wait(self) -> None:
        graph = _graph(
            [
                _zone("S", start=True),
                _zone("A", max_drones=2),
                _zone("G", end=True),
            ],
            [("S", "A"), ("A", "G")],
            link_capacity=1,
        )
        sim = Simulation(graph, [_drone(1, "S", "G"), _drone(2, "S", "G")])

        first = sim.step()

        assert first.movements == [
            Movement(
                drone_id=1, from_zone="S", to_zone="A", turns_required=1
            )
        ]
        assert len(first.conflicts) == 1
        assert "drone 2" in first.conflicts[0]
        assert "link" in first.conflicts[0]
        assert sim.state.drones[2].status == DroneStatus.WAITING

    def test_restricted_link_is_not_reused_while_held(self) -> None:
        graph = _graph(
            [
                _zone("S", start=True),
                _zone("R", ZoneType.RESTRICTED),
                _zone("G", end=True),
            ],
            [("S", "R"), ("R", "G")],
            link_capacity=1,
        )
        sim = Simulation(graph, [_drone(1, "S", "G"), _drone(2, "S", "G")])

        first = sim.step()
        assert sim.state.link_usage[("S", "R")] == 1
        assert len(first.conflicts) == 1
        assert "drone 2" in first.conflicts[0]

        second = sim.step()
        assert sim.state.link_usage[("S", "R")] == 1
        assert len(second.conflicts) == 1

    def test_drones_processed_in_id_order(self) -> None:
        graph = _graph(
            [
                _zone("S", start=True),
                _zone("A", max_drones=2),
                _zone("G", end=True),
            ],
            [("S", "A"), ("A", "G")],
            link_capacity=2,
        )
        sim = Simulation(graph, [_drone(1, "S", "G"), _drone(2, "S", "G")])

        first = sim.step()

        assert [m.drone_id for m in first.movements] == [1, 2]
        assert len(first.conflicts) == 0

    def test_empty_fleet_is_finished(self) -> None:
        graph = _graph(
            [_zone("S", start=True), _zone("G", end=True)],
            [("S", "G")],
        )
        sim = Simulation(graph, [])

        assert sim.finished

    def test_head_on_collision_respect_link_capacity(self) -> None:
        graph = _graph(
            [_zone("A"), _zone("B")],
            [("A", "B")],
            link_capacity=1,
        )

        drones = [_drone(1, "A", "B"), _drone(2, "B", "A")]
        sim = Simulation(graph, drones)

        first = sim.step()

        assert len(first.movements) == 1
        assert first.movements[0].drone_id == 1
        assert len(first.conflicts) == 1
        assert "drone 2" in first.conflicts[0]
        assert "link" in first.conflicts[0]
