"""Tests for the quickest-flow planner (homogeneous fleets)."""

from __future__ import annotations

from src.models import Drone, Graph
from src.parser.parser import parse_map
from src.parser.converter import build_graph
from src.simulation.flow import Dinic, FlowPlanner, _Network, _INF
from src.simulation.planner import Planner, _cost_consistent


class TestDinic:
    """Max-flow and path-decomposition correctness on small networks."""

    def test_two_disjoint_paths(self) -> None:
        d = Dinic(4)
        d.add_edge(0, 1, 1)
        d.add_edge(1, 3, 1)
        d.add_edge(0, 2, 1)
        d.add_edge(2, 3, 1)
        assert d.max_flow(0, 3) == 2

    def test_decompose_recovers_unit_paths(self) -> None:
        d = Dinic(4)
        d.add_edge(0, 1, 1)
        d.add_edge(1, 3, 1)
        d.add_edge(0, 2, 1)
        d.add_edge(2, 3, 1)
        flow = d.max_flow(0, 3)
        paths = d.decompose(0, 3, flow)
        assert sorted(paths) == [[0, 1, 3], [0, 2, 3]]

    def test_serial_bottleneck(self) -> None:
        # s -> a (cap 2), a -> t (cap 1): flow = 1.
        d = Dinic(3)
        d.add_edge(0, 1, 2)
        d.add_edge(1, 2, 1)
        assert d.max_flow(0, 2) == 1

    def test_decompose_with_larger_capacity(self) -> None:
        d = Dinic(3)
        d.add_edge(0, 1, 3)
        d.add_edge(1, 2, 3)
        assert d.max_flow(0, 2) == 3
        paths = d.decompose(0, 2, 3)
        assert len(paths) == 3
        assert all(p == [0, 1, 2] for p in paths)


class TestFlowPlanner:
    """Optimal-makespan schedules on homogeneous fleets."""

    def _graph_drones(
        self, path: str
    ) -> tuple[Graph, list[Drone]]:
        return build_graph(parse_map(path))

    def test_simple_line_map(self) -> None:
        graph, drones = self._graph_drones("maps/personal/simple_line.txt")
        schedule, blocked = FlowPlanner(graph).plan(drones)
        assert not blocked
        assert schedule.makespan == 7
        assert schedule.is_conflict_free()

    def test_linear_path_tier(self) -> None:
        graph, drones = self._graph_drones("maps/easy/01_linear_path.txt")
        schedule, _ = FlowPlanner(graph).plan(drones)
        assert schedule.makespan == 5
        assert schedule.is_conflict_free()

    def test_maze_nightmare_tier(self) -> None:
        graph, drones = self._graph_drones(
            "maps/hard/01_maze_nightmare.txt"
        )
        schedule, _ = FlowPlanner(graph).plan(drones)
        assert schedule.makespan == 14
        assert schedule.is_conflict_free()

    def test_schedule_is_deterministic(self) -> None:
        graph, drones = self._graph_drones("maps/personal/simple_line.txt")
        s1, _ = FlowPlanner(graph).plan(drones)
        s2, _ = FlowPlanner(graph).plan(drones)
        assert s1.makespan == s2.makespan
        assert s1.actions == s2.actions

    def test_cost_consistent_on_all_normal_map(self) -> None:
        graph, drones = self._graph_drones("maps/personal/simple_line.txt")
        schedule, _ = FlowPlanner(graph).plan(drones)
        assert _cost_consistent(schedule, graph)


class TestPlannerDispatch:
    """Flow is primary for homogeneous; CBS handles the rest."""

    def test_homogeneous_uses_flow_schedule(self) -> None:
        graph, drones = build_graph(
            parse_map("maps/personal/simple_line.txt")
        )
        schedule, blocked = Planner(graph).plan(drones)
        assert not blocked
        assert schedule.makespan == 7
        assert schedule.is_conflict_free()

    def test_restricted_map_falls_back_to_cbs(self) -> None:
        # bottleneck has restricted chokes: the flow splices, so the
        # planner must fall back to CBS and still give the optimal 11.
        graph, drones = build_graph(
            parse_map("maps/personal/bottleneck.txt")
        )
        schedule, blocked = Planner(graph).plan(drones)
        assert not blocked
        assert schedule.makespan == 11
        assert schedule.is_conflict_free()

    def test_heterogeneous_uses_cbs(self) -> None:
        graph, drones = build_graph(
            parse_map("maps/personal/parallel_paths.txt")
        )
        # Force a heterogeneous fleet: swap two drones' targets.
        drones[0].target_zone, drones[1].target_zone = (
            drones[1].target_zone,
            drones[0].target_zone,
        )
        schedule, blocked = Planner(graph).plan(drones)
        assert not blocked
        assert schedule.is_conflict_free()