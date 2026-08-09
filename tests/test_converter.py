"""Tests for the parser-to-domain converter (Phase 2)."""

from __future__ import annotations

import pytest

from src.models import (
    Connection,
    DroneStatus,
    ParsedConnection,
    ParsedMap,
    ParsedZone,
    Zone,
    ZoneType,
)
from src.parser.converter import (
    _convert_connection,
    _convert_zone,
    build_graph,
)
from src.parser.errors import ParseError


def _make_zone(
    name: str,
    x: int = 0,
    y: int = 0,
    metadata: dict[str, str] | None = None,
    line_number: int = 1,
) -> ParsedZone:
    """Build a ParsedZone with sensible test defaults."""
    return ParsedZone(
        name=name,
        x=x,
        y=y,
        metadata=metadata if metadata is not None else {},
        line_number=line_number,
    )


def _make_conn(
    zone_a: str,
    zone_b: str,
    metadata: dict[str, str] | None = None,
    line_number: int = 1,
) -> ParsedConnection:
    """Build a ParsedConnection with sensible test defaults."""
    return ParsedConnection(
        zone_a=zone_a,
        zone_b=zone_b,
        metadata=metadata if metadata is not None else {},
        line_number=line_number,
    )


class TestConvertZone:
    """Unit tests for the zone conversion helper."""

    def test_defaults(self) -> None:
        zone = _convert_zone(_make_zone("A"), False, False)
        assert zone == Zone(name="A", x=0, y=0)

    def test_preserves_x_and_y(self) -> None:
        zone = _convert_zone(_make_zone("A", x=5, y=7), False, False)
        assert zone.x == 5
        assert zone.y == 7

    def test_invalid_name_raises_error(self) -> None:
        parsed = _make_zone("my-zone", line_number=3)
        with pytest.raises(ParseError) as exc:
            _convert_zone(parsed, False, False)
        assert exc.value.line_number == 3

    def test_explicit_zone_type(self) -> None:
        parsed = _make_zone("A", metadata={"zone": "priority"})
        zone = _convert_zone(parsed, False, False)
        assert zone.zone_type == ZoneType.PRIORITY

    def test_all_zone_types(self) -> None:
        for token, expected in [
            ("normal", ZoneType.NORMAL),
            ("priority", ZoneType.PRIORITY),
            ("restricted", ZoneType.RESTRICTED),
            ("blocked", ZoneType.BLOCKED),
        ]:
            parsed = _make_zone("A", metadata={"zone": token})
            zone = _convert_zone(parsed, False, False)
            assert zone.zone_type == expected

    def test_unknown_zone_type_raises_error(self) -> None:
        parsed = _make_zone("A", metadata={"zone": "bogus"}, line_number=7)
        with pytest.raises(ParseError) as exc:
            _convert_zone(parsed, False, False)
        assert exc.value.line_number == 7

    def test_max_drones(self) -> None:
        parsed = _make_zone("A", metadata={"max_drones": "4"})
        zone = _convert_zone(parsed, False, False)
        assert zone.max_drones == 4

    def test_max_drones_non_integer_raises_error(self) -> None:
        parsed = _make_zone("A", metadata={"max_drones": "abc"}, line_number=3)
        with pytest.raises(ParseError) as exc:
            _convert_zone(parsed, False, False)
        assert exc.value.line_number == 3

    def test_max_drones_below_one_raises_error(self) -> None:
        parsed = _make_zone("A", metadata={"max_drones": "0"}, line_number=4)
        with pytest.raises(ParseError) as exc:
            _convert_zone(parsed, False, False)
        assert exc.value.line_number == 4

    def test_color(self) -> None:
        parsed = _make_zone("A", metadata={"color": "red"})
        zone = _convert_zone(parsed, False, False)
        assert zone.color == "red"

    def test_start_hub_flag(self) -> None:
        zone = _convert_zone(_make_zone("A"), True, False)
        assert zone.is_start_hub is True
        assert zone.is_end_hub is False
        assert zone.capacity is None

    def test_end_hub_flag(self) -> None:
        zone = _convert_zone(_make_zone("A"), False, True)
        assert zone.is_end_hub is True
        assert zone.capacity is None

    def test_regular_zone_capacity(self) -> None:
        parsed = _make_zone("A", metadata={"max_drones": "2"})
        zone = _convert_zone(parsed, False, False)
        assert zone.capacity == 2


class TestConvertConnection:
    """Unit tests for the connection conversion helper."""

    def test_default_capacity(self) -> None:
        parsed = _make_conn("A", "B")
        conn = _convert_connection(parsed, {"A", "B"})
        assert conn == Connection(zone_a="A", zone_b="B")

    def test_explicit_capacity(self) -> None:
        parsed = _make_conn("A", "B", {"max_link_capacity": "3"})
        conn = _convert_connection(parsed, {"A", "B"})
        assert conn.max_link_capacity == 3

    def test_unknown_endpoint_raises_error(self) -> None:
        parsed = _make_conn("A", "X", line_number=5)
        with pytest.raises(ParseError) as exc:
            _convert_connection(parsed, {"A", "B"})
        assert exc.value.line_number == 5

    def test_unknown_zone_a_raises_error(self) -> None:
        parsed = _make_conn("X", "B", line_number=6)
        with pytest.raises(ParseError) as exc:
            _convert_connection(parsed, {"A", "B"})
        assert exc.value.line_number == 6

    def test_non_integer_capacity_raises_error(self) -> None:
        parsed = _make_conn("A", "B", {"max_link_capacity": "x"}, 6)
        with pytest.raises(ParseError) as exc:
            _convert_connection(parsed, {"A", "B"})
        assert exc.value.line_number == 6

    def test_capacity_below_one_raises_error(self) -> None:
        parsed = _make_conn("A", "B", {"max_link_capacity": "0"}, 7)
        with pytest.raises(ParseError) as exc:
            _convert_connection(parsed, {"A", "B"})
        assert exc.value.line_number == 7


class TestBuildGraph:
    """Integration tests for build_graph."""

    def test_minimal_map(self) -> None:
        parsed = ParsedMap(
            nb_drones=3,
            start_hub=_make_zone("start", line_number=2),
            end_hub=_make_zone("end", line_number=3),
        )
        graph, drones = build_graph(parsed)
        assert set(graph.zones) == {"start", "end"}
        assert graph.connections == {}
        assert len(drones) == 3

    def test_full_map(self) -> None:
        zones = [
            _make_zone("roof1", metadata={"max_drones": "2"}, line_number=3),
            _make_zone(
                "corridorA",
                metadata={"zone": "priority", "color": "blue"},
                line_number=4,
            ),
        ]
        connections = [
            ParsedConnection(
                zone_a="base",
                zone_b="roof1",
                metadata={"max_link_capacity": "3"},
                line_number=6,
            ),
            ParsedConnection(
                zone_a="roof1", zone_b="corridorA", line_number=7
            ),
            ParsedConnection(
                zone_a="corridorA", zone_b="target", line_number=8
            ),
        ]
        parsed = ParsedMap(
            nb_drones=5,
            start_hub=_make_zone(
                "base", metadata={"color": "green"}, line_number=2
            ),
            end_hub=_make_zone("target", line_number=5),
            zones=zones,
            connections=connections,
        )
        graph, drones = build_graph(parsed)
        assert graph.zones["base"].is_start_hub is True
        assert graph.zones["base"].color == "green"
        assert graph.zones["target"].is_end_hub is True
        assert graph.zones["roof1"].max_drones == 2
        assert graph.zones["corridorA"].zone_type == ZoneType.PRIORITY
        assert graph.zones["corridorA"].color == "blue"
        assert graph.connections[("base", "roof1")].max_link_capacity == 3
        assert ("corridorA", "roof1") in graph.connections
        assert ("corridorA", "target") in graph.connections
        assert graph.neighbors("base") == ["roof1"]
        assert graph.neighbors("corridorA") == ["roof1", "target"]
        assert len(drones) == 5

    def test_all_zone_types(self) -> None:
        zones = [
            _make_zone("z_normal", metadata={"zone": "normal"}, line_number=4),
            _make_zone(
                "z_priority", metadata={"zone": "priority"}, line_number=5
            ),
            _make_zone(
                "z_restricted",
                metadata={"zone": "restricted"},
                line_number=6,
            ),
            _make_zone(
                "z_blocked", metadata={"zone": "blocked"}, line_number=7
            ),
        ]
        parsed = ParsedMap(
            nb_drones=1,
            start_hub=_make_zone("start", line_number=2),
            end_hub=_make_zone("end", line_number=3),
            zones=zones,
        )
        graph, _ = build_graph(parsed)
        assert graph.zones["z_normal"].zone_type == ZoneType.NORMAL
        assert graph.zones["z_priority"].zone_type == ZoneType.PRIORITY
        assert graph.zones["z_restricted"].zone_type == ZoneType.RESTRICTED
        assert graph.zones["z_blocked"].zone_type == ZoneType.BLOCKED

    def test_connection_key_canonicalized(self) -> None:
        zones = [
            _make_zone("A", line_number=4),
            _make_zone("B", line_number=5),
        ]
        parsed = ParsedMap(
            nb_drones=1,
            start_hub=_make_zone("start", line_number=2),
            end_hub=_make_zone("end", line_number=3),
            zones=zones,
            connections=[
                ParsedConnection(
                    zone_a="B", zone_b="A", line_number=6
                ),
            ],
        )
        graph, _ = build_graph(parsed)
        assert ("A", "B") in graph.connections
        assert graph.connections[("A", "B")].zone_a == "B"
        assert graph.neighbors("A") == ["B"]
        assert graph.neighbors("B") == ["A"]

    def test_duplicate_connection_raises_error(self) -> None:
        zones = [
            _make_zone("A", line_number=4),
            _make_zone("B", line_number=5),
        ]
        parsed = ParsedMap(
            nb_drones=1,
            start_hub=_make_zone("start", line_number=2),
            end_hub=_make_zone("end", line_number=3),
            zones=zones,
            connections=[
                ParsedConnection(zone_a="A", zone_b="B", line_number=6),
                ParsedConnection(zone_a="B", zone_b="A", line_number=7),
            ],
        )
        with pytest.raises(ParseError) as exc:
            build_graph(parsed)
        assert exc.value.line_number == 7

    def test_duplicate_zone_name_raises_error(self) -> None:
        parsed = ParsedMap(
            nb_drones=1,
            start_hub=_make_zone("A", line_number=2),
            end_hub=_make_zone("end", line_number=3),
            zones=[_make_zone("A", line_number=4)],
        )
        with pytest.raises(ParseError) as exc:
            build_graph(parsed)
        assert exc.value.line_number == 4

    def test_start_end_same_name_raises_error(self) -> None:
        parsed = ParsedMap(
            nb_drones=1,
            start_hub=_make_zone("A", line_number=2),
            end_hub=_make_zone("A", line_number=4),
        )
        with pytest.raises(ParseError) as exc:
            build_graph(parsed)
        assert exc.value.line_number == 4

    def test_unknown_zone_type_raises_error(self) -> None:
        parsed = ParsedMap(
            nb_drones=1,
            start_hub=_make_zone("start", line_number=2),
            end_hub=_make_zone("end", line_number=3),
            zones=[_make_zone("A", metadata={"zone": "bogus"}, line_number=4)],
        )
        with pytest.raises(ParseError) as exc:
            build_graph(parsed)
        assert exc.value.line_number == 4

    def test_unknown_connection_endpoint_raises_error(self) -> None:
        parsed = ParsedMap(
            nb_drones=1,
            start_hub=_make_zone("start", line_number=2),
            end_hub=_make_zone("end", line_number=3),
            connections=[
                ParsedConnection(
                    zone_a="start", zone_b="ghost", line_number=4
                ),
            ],
        )
        with pytest.raises(ParseError) as exc:
            build_graph(parsed)
        assert exc.value.line_number == 4

    def test_unknown_connection_zone_a_raises_error(self) -> None:
        parsed = ParsedMap(
            nb_drones=1,
            start_hub=_make_zone("start", line_number=2),
            end_hub=_make_zone("end", line_number=3),
            connections=[
                ParsedConnection(
                    zone_a="ghost", zone_b="end", line_number=5
                ),
            ],
        )
        with pytest.raises(ParseError) as exc:
            build_graph(parsed)
        assert exc.value.line_number == 5


class TestDroneFleet:
    """Tests for the drone fleet produced by build_graph."""

    def test_drone_count_and_ids(self) -> None:
        parsed = ParsedMap(
            nb_drones=4,
            start_hub=_make_zone("start", line_number=2),
            end_hub=_make_zone("end", line_number=3),
        )
        _, drones = build_graph(parsed)
        assert [drone.id for drone in drones] == [1, 2, 3, 4]

    def test_drone_initial_state(self) -> None:
        parsed = ParsedMap(
            nb_drones=2,
            start_hub=_make_zone("start", line_number=2),
            end_hub=_make_zone("end", line_number=3),
        )
        _, drones = build_graph(parsed)
        for drone in drones:
            assert drone.current_zone == "start"
            assert drone.target_zone == "end"
            assert drone.status == DroneStatus.WAITING
            assert drone.path == []
