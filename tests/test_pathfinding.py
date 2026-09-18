"""Tests for time-expanded pathfinding: dist_to_goal and find_path_timed."""

from __future__ import annotations

from src.models import Graph, Zone, Connection, ZoneType
from src.models.graph_utils import canonical_key
from src.simulation.pathfinding import (
    dist_to_goal,
    find_path_timed,
    VertexConstraint,
    LinkConstraint,
)


# --- Constraints helper ---
def no_constraints() -> tuple[set[VertexConstraint], set[LinkConstraint]]:
    return set(), set()


# Type alias for constraints tuple
Constraints = tuple[set[VertexConstraint], set[LinkConstraint]]


# --- dist_to_goal tests ---

class TestDistToGoal:
    """Reverse Dijkstra heuristic table."""

    def test_simple_line(self, simple_graph: Graph) -> None:
        dist = dist_to_goal(simple_graph, "G")
        assert dist["G"] == 0
        assert dist["A"] == 1
        assert dist["S"] == 2

    def test_restricted_costs_two(self, restricted_graph: Graph) -> None:
        dist = dist_to_goal(restricted_graph, "G")
        assert dist["G"] == 0
        assert dist["R"] == 2
        assert dist["S"] == 3

    def test_blocked_zone_infinite(self, blocked_zone_graph: Graph) -> None:
        dist = dist_to_goal(blocked_zone_graph, "G")
        assert dist["A"] == float("inf")
        assert dist["B"] == 1
        assert dist["S"] == 2

    def test_unreachable_goal_infinite(
            self, disconnected_graph: Graph) -> None:
        dist = dist_to_goal(disconnected_graph, "G")
        assert dist["G"] == 0
        assert dist["S"] == float("inf")


# --- find_path_timed tests ---

class TestFindPathTimed:
    """Time-expanded A* returning TimedRoute =
    list[tuple[zone, arrival_turn]]."""

    def test_direct_line(self, simple_graph: Graph) -> None:
        """S-A-G: start_turn=1 -> arrive G at turn 3."""
        dist = dist_to_goal(simple_graph, "G")
        route = find_path_timed(
            simple_graph, "S", "G", *no_constraints(),
            start_turn=1, horizon=10, dist=dist
        )
        assert route is not None
        assert route == [("S", 1), ("A", 2), ("G", 3)]

    def test_both_endpoints_in_route(self, simple_graph: Graph) -> None:
        dist = dist_to_goal(simple_graph, "G")
        route = find_path_timed(
            simple_graph, "S", "G", *no_constraints(),
            start_turn=1, horizon=10, dist=dist
        )
        assert route is not None
        assert route[0][0] == "S"
        assert route[-1][0] == "G"

    def test_avoid_restricted_when_cheaper(
            self, restricted_alternative_graph: Graph) -> None:
        """S-A-G (cost 2) preferred over S-R-G (cost 3)."""
        dist = dist_to_goal(restricted_alternative_graph, "G")
        route = find_path_timed(
            restricted_alternative_graph, "S", "G", *no_constraints(),
            start_turn=1, horizon=10, dist=dist
        )
        assert route is not None
        zones = [z for z, _ in route]
        assert "R" not in zones
        assert "A" in zones

    def test_use_restricted_when_only_route(
            self, restricted_graph: Graph) -> None:
        """S -> R(restricted) -> G is only path."""
        dist = dist_to_goal(restricted_graph, "G")
        route = find_path_timed(
            restricted_graph, "S", "G", *no_constraints(),
            start_turn=1, horizon=10, dist=dist
        )
        assert route is not None
        zones_seq = [z for z, _ in route]
        assert "R" in zones_seq
        assert route == [("S", 1), ("R", 3), ("G", 4)]

    def test_detour_blocked(self, blocked_zone_graph: Graph) -> None:
        """Blocked zone A skipped, takes S-B-G."""
        dist = dist_to_goal(blocked_zone_graph, "G")
        route = find_path_timed(
            blocked_zone_graph, "S", "G", *no_constraints(),
            start_turn=1, horizon=10, dist=dist
        )
        assert route is not None
        zones = [z for z, _ in route]
        assert "A" not in zones
        assert "B" in zones

    def test_none_unreachable(self, disconnected_graph: Graph) -> None:
        """No spatial path returns None."""
        dist = dist_to_goal(disconnected_graph, "G")
        route = find_path_timed(
            disconnected_graph, "S", "G", *no_constraints(),
            start_turn=1, horizon=10, dist=dist
        )
        assert route is None

    def test_none_blocked_goal(self) -> None:
        """Goal zone is blocked -> None."""
        zones = {
            "S": Zone(name="S", x=0, y=0, zone_type=ZoneType.NORMAL,
                      is_start_hub=True, max_drones=1),
            "G": Zone(name="G", x=1, y=0, zone_type=ZoneType.BLOCKED,
                      max_drones=1),
        }
        connections = {
            canonical_key("S", "G"): Connection(
                zone_a="S", zone_b="G", max_link_capacity=1),
        }
        graph = Graph(zones=zones, connections=connections)
        dist = dist_to_goal(graph, "G")
        route = find_path_timed(graph, "S", "G", *no_constraints(),
                                start_turn=1, horizon=10, dist=dist)
        assert route is None

    def test_prefer_priority_on_ties(self, priority_tie_graph: Graph) -> None:
        """Both routes cost 2, priority route (via P) preferred."""
        dist = dist_to_goal(priority_tie_graph, "G")
        route = find_path_timed(
            priority_tie_graph, "S", "G", *no_constraints(),
            start_turn=1, horizon=10, dist=dist
        )
        assert route is not None
        zones = [z for z, _ in route]
        assert "P" in zones
        assert "N" not in zones

    def test_shortest_beats_longer_priority(
            self, priority_longer_graph: Graph) -> None:
        """Cost 2 (normal) beats cost 3 (priority) even with priority zones."""
        dist = dist_to_goal(priority_longer_graph, "G")
        route = find_path_timed(
            priority_longer_graph, "S", "G", *no_constraints(),
            start_turn=1, horizon=10, dist=dist
        )
        assert route is not None
        zones = [z for z, _ in route]
        assert "N" in zones
        assert "P" not in zones

    def test_start_equals_goal(self, simple_graph: Graph) -> None:
        """Start == goal returns [(start, start_turn)]."""
        dist = dist_to_goal(simple_graph, "S")
        route = find_path_timed(
            simple_graph, "S", "S", *no_constraints(),
            start_turn=5, horizon=10, dist=dist
        )
        assert route == [("S", 5)]


class TestFindPathTimedWithConstraints:
    """Time-expanded A* with vertex/link constraints."""

    def test_vertex_constraint_avoids_zone_at_turn(
            self, simple_graph: Graph) -> None:
        """VertexConstraint on A at turn 2 forces wait."""
        dist = dist_to_goal(simple_graph, "G")
        constraints: Constraints = (
            {VertexConstraint(zone="A", turn=2)}, set())
        route = find_path_timed(
            simple_graph, "S", "G", *constraints,
            start_turn=1, horizon=10, dist=dist
        )
        assert route is not None
        assert route == [("S", 1), ("S", 2), ("A", 3), ("G", 4)]

    def test_link_constraint_avoids_link_during_transit(
            self, simple_graph: Graph) -> None:
        """LinkConstraint on S-A during turn 1 forces wait."""
        dist = dist_to_goal(simple_graph, "G")
        constraints: Constraints = (
            set(), {LinkConstraint(link=canonical_key("S", "A"), turn=1)})
        route = find_path_timed(
            simple_graph, "S", "G", *constraints,
            start_turn=1, horizon=10, dist=dist
        )
        assert route is not None
        assert route == [("S", 1), ("S", 2), ("A", 3), ("G", 4)]

    def test_horizon_cutoff(self, simple_graph: Graph) -> None:
        """Horizon too small returns None."""
        dist = dist_to_goal(simple_graph, "G")
        route = find_path_timed(
            simple_graph, "S", "G", *no_constraints(),
            start_turn=1, horizon=2, dist=dist
        )
        assert route is None
