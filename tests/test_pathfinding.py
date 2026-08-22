"""Tests for the hand-written weighted pathfinder (engine milestone).

``find_path`` returns the zone list for the cheapest start->goal route
under the map's zone-type costs, preferring priority zones on equal
cost, and ``None`` when no route exists.
"""

from __future__ import annotations

from src.models import Connection, Graph, Zone, ZoneType
from src.simulation.pathfinding import find_path


def _zone(
    name: str,
    ztype: ZoneType = ZoneType.NORMAL,
    start: bool = False,
    end: bool = False,
) -> Zone:
    """Build a Zone with the given type and hub flags."""
    return Zone(
        name=name,
        x=0,
        y=0,
        zone_type=ztype,
        is_start_hub=start,
        is_end_hub=end,
    )


def _graph(
    zones: list[Zone], edges: list[tuple[str, str]]
) -> Graph:
    """Build a Graph connecting the given zones with default links."""
    connections: dict[tuple[str, str], Connection] = {}
    for zone_a, zone_b in edges:
        key = (zone_a, zone_b) if zone_a <= zone_b else (zone_b, zone_a)
        connections[key] = Connection(zone_a=key[0], zone_b=key[1])
    return Graph(
        zones={zone.name: zone for zone in zones},
        connections=connections,
    )


class TestFindPath:
    """Weighted shortest-path behaviour under zone-type costs."""

    def test_finds_direct_line(self) -> None:
        graph = _graph(
            [_zone("S", start=True), _zone("A"), _zone("G", end=True)],
            [("S", "A"), ("A", "G")],
        )

        assert find_path(graph, "S", "G") == ["S", "A", "G"]

    def test_includes_both_endpoints(self) -> None:
        graph = _graph(
            [
                _zone("S", start=True),
                _zone("A"),
                _zone("B"),
                _zone("G", end=True),
            ],
            [("S", "A"), ("A", "B"), ("B", "G")],
        )

        path = find_path(graph, "S", "G")

        assert path[0] == "S"
        assert path[-1] == "G"

    def test_avoids_restricted_zone_when_cheaper_route_exists(
        self,
    ) -> None:
        zones = [
            _zone("S", start=True),
            _zone("G", end=True),
            _zone("A"),
            _zone("R", ZoneType.RESTRICTED),
        ]
        graph = _graph(
            zones, [("S", "A"), ("A", "G"), ("S", "R"), ("R", "G")]
        )

        assert find_path(graph, "S", "G") == ["S", "A", "G"]

    def test_uses_restricted_zone_when_it_is_the_only_route(
        self,
    ) -> None:
        zones = [
            _zone("S", start=True),
            _zone("G", end=True),
            _zone("R", ZoneType.RESTRICTED),
        ]
        graph = _graph(zones, [("S", "R"), ("R", "G")])

        assert find_path(graph, "S", "G") == ["S", "R", "G"]

    def test_detours_around_blocked_zone(self) -> None:
        zones = [
            _zone("S", start=True),
            _zone("G", end=True),
            _zone("N"),
            _zone("B", ZoneType.BLOCKED),
        ]
        graph = _graph(
            zones, [("S", "N"), ("N", "G"), ("S", "B"), ("B", "G")]
        )

        assert find_path(graph, "S", "G") == ["S", "N", "G"]

    def test_returns_none_when_goal_unreachable(self) -> None:
        zones = [_zone("S", start=True), _zone("G", end=True), _zone("A")]
        graph = _graph(zones, [("S", "A")])

        assert find_path(graph, "S", "G") is None

    def test_returns_none_when_goal_is_blocked(self) -> None:
        zones = [_zone("S", start=True), _zone("A", ZoneType.BLOCKED)]
        graph = _graph(zones, [("S", "A")])

        assert find_path(graph, "S", "A") is None

    def test_prefers_priority_zone_on_equal_cost(self) -> None:
        zones = [
            _zone("S", start=True),
            _zone("G", end=True),
            _zone("A"),
            _zone("P", ZoneType.PRIORITY),
        ]
        graph = _graph(
            zones, [("S", "A"), ("A", "G"), ("S", "P"), ("P", "G")]
        )

        assert find_path(graph, "S", "G") == ["S", "P", "G"]

    def test_shortest_path_beats_longer_priority_route(self) -> None:
        zones = [
            _zone("S", start=True),
            _zone("G", end=True),
            _zone("A"),
            _zone("P", ZoneType.PRIORITY),
            _zone("B"),
        ]
        graph = _graph(
            zones,
            [("S", "A"), ("A", "G"), ("S", "P"), ("P", "B"), ("B", "G")],
        )

        assert find_path(graph, "S", "G") == ["S", "A", "G"]

    def test_start_equals_goal(self) -> None:
        graph = _graph([_zone("S", start=True), _zone("A")], [("S", "A")])

        assert find_path(graph, "S", "S") == ["S"]