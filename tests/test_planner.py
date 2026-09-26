"""Tests for the CBS Planner — optimal makespan schedules."""

from __future__ import annotations

from collections.abc import Callable

from src.models import Drone, Graph
from src.parser.parser import parse_map
from src.parser.converter import build_graph
from src.simulation.planner import Planner


class TestPlannerMakespan:
    """Optimal makespan assertions for test matrix."""

    def test_bottleneck_map(self) -> None:
        graph, drones = build_graph(parse_map("maps/personal/bottleneck.txt"))
        schedule, blocked = Planner(graph).plan(drones)
        assert not blocked
        assert schedule.makespan == 11

    def test_example_map(self) -> None:
        graph, drones = build_graph(parse_map("maps/personal/example.txt"))
        schedule, blocked = Planner(graph).plan(drones)
        assert not blocked
        assert schedule.makespan == 4

    def test_parallel_paths_map(self) -> None:
        graph, drones = build_graph(
            parse_map("maps/personal/parallel_paths.txt")
        )
        schedule, blocked = Planner(graph).plan(drones)
        assert not blocked
        assert schedule.makespan == 9

    def test_priority_blocked_map(self) -> None:
        graph, drones = build_graph(
            parse_map("maps/personal/priority_blocked.txt")
        )
        schedule, blocked = Planner(graph).plan(drones)
        assert not blocked
        assert schedule.makespan == 8

    def test_complex_cycle_map(self) -> None:
        graph, drones = build_graph(
            parse_map("maps/personal/complex_cycle.txt")
        )
        schedule, blocked = Planner(graph).plan(drones)
        assert not blocked
        assert schedule.makespan == 9

    def test_simple_line_map(self) -> None:
        graph, drones = build_graph(
            parse_map("maps/personal/simple_line.txt")
        )
        schedule, blocked = Planner(graph).plan(drones)
        assert not blocked
        assert schedule.makespan == 7


class TestPlannerSynthetic:
    """Synthetic unit tests for core CBS behaviors."""

    def test_single_drone_normal_route(
        self,
        simple_graph: Graph,
        drones_at_start: Callable[..., list[Drone]],
    ) -> None:
        drones = drones_at_start(1, "S", "G")
        schedule, _ = Planner(simple_graph).plan(drones)
        assert schedule.makespan == 3

    def test_single_drone_restricted_route(
        self,
        restricted_graph: Graph,
        drones_at_start: Callable[..., list[Drone]],
    ) -> None:
        drones = drones_at_start(1, "S", "G")
        schedule, _ = Planner(restricted_graph).plan(drones)
        assert schedule.makespan == 4

    def test_split_routes_two_drones(
        self,
        split_graph: Graph,
        drones_at_start: Callable[..., list[Drone]],
    ) -> None:
        drones = drones_at_start(2, "S", "G")
        schedule, _ = Planner(split_graph).plan(drones)
        assert schedule.makespan == 3

    def test_head_on_collision_link_cap1(self, head_on_graph: Graph) -> None:
        drones = [
            Drone(id=1, current_zone="A", target_zone="B"),
            Drone(id=2, current_zone="B", target_zone="A"),
        ]
        schedule, _ = Planner(head_on_graph).plan(drones)
        assert schedule.makespan == 3


class TestPlannerConflictFree:
    """Verify schedule respects all capacity constraints."""

    def test_no_zone_over_capacity(
        self,
        bottleneck_graph: Graph,
        drones_at_start: Callable[..., list[Drone]],
    ) -> None:
        drones = drones_at_start(3)
        schedule, _ = Planner(bottleneck_graph).plan(drones)
        assert schedule.is_conflict_free()

    def test_no_link_over_capacity(
        self,
        bottleneck_graph: Graph,
        drones_at_start: Callable[..., list[Drone]],
    ) -> None:
        drones = drones_at_start(3)
        schedule, _ = Planner(bottleneck_graph).plan(drones)
        assert schedule.is_conflict_free()

    def test_post_arrival_occupancy(
        self,
        finite_goal_graph: Graph,
        drones_at_start: Callable[..., list[Drone]],
    ) -> None:
        """Arrived drone occupies finite-capacity goal for all future turns."""
        drones = drones_at_start(1)
        schedule, _ = Planner(finite_goal_graph).plan(drones)
        assert schedule.occupies_goal_after_arrival()


class TestPlannerUnreachable:
    """Drones with no spatial route are marked BLOCKED."""

    def test_unreachable_goal_blocks_drones(
        self,
        disconnected_graph: Graph,
        drones_at_start: Callable[..., list[Drone]],
    ) -> None:
        drones = drones_at_start(1)
        _, blocked = Planner(disconnected_graph).plan(drones)
        assert len(blocked) == 1
        assert blocked[0].id == 1
        assert blocked[0].blocked_reason is not None
        assert "no route" in blocked[0].blocked_reason.lower()


class TestPlannerDeterminism:
    """Same input always produces same schedule."""

    def test_deterministic_output(
        self,
        split_graph: Graph,
        drones_at_start: Callable[..., list[Drone]],
    ) -> None:
        drones = drones_at_start(3)
        s1, _ = Planner(split_graph).plan(drones)
        s2, _ = Planner(split_graph).plan(drones)

        assert s1 == s2
