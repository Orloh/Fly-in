"""Tests for the CLI output layer.

Pure formatter tests + simulate integration tests reusing engine helpers.
"""

from __future__ import annotations

from src.models import (
    Connection,
    Drone,
    DroneStatus,
    Graph,
    Movement,
    ParsedConnection,
    ParsedMap,
    ParsedZone,
    TurnResult,
    Zone,
    ZoneType,
)
from src.simulation.engine import Simulation
from src.cli import (
    PALETTE,
    paint,
    format_map,
    format_turn,
    simulate,
    run,
)


def _zone(
    name: str,
    ztype: ZoneType = ZoneType.NORMAL,
    max_drones: int = 1,
    start: bool = False,
    end: bool = False,
) -> Zone:
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
    return Drone(id=drone_id, current_zone=current, target_zone=target)


def _graph(
    zones: list[Zone],
    edges: list[tuple[str, str]],
    link_capacity: int = 1,
) -> Graph:
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


def _parsed_zone(name: str, x: int, y: int, meta: dict[str, str] = None) -> ParsedZone:
    return ParsedZone(
        name=name,
        x=x,
        y=y,
        metadata=meta or {},
        line_number=1,
    )


def _parsed_conn(a: str, b: str, meta: dict[str, str] = None) -> ParsedConnection:
    return ParsedConnection(
        zone_a=a,
        zone_b=b,
        metadata=meta or {},
        line_number=1,
    )


def _parsed_map(nb_drones: int, zones: list[ParsedZone], conns: list[ParsedConnection]) -> ParsedMap:
    return ParsedMap(
        nb_drones=nb_drones,
        start_hub=zones[0],
        end_hub=zones[1],
        zones=zones[2:],
        connections=conns,
    )


class TestFormatTurn:
    def test_single_movement(self) -> None:
        result = Movement(drone_id=1, from_zone="S", to_zone="A", turns_required=1)
        turn = TurnResult(turn_number=1, movements=[result])
        assert format_turn(turn) == "D1-A"

    def test_multiple_movements_id_order(self) -> None:
        m1 = Movement(drone_id=2, from_zone="S", to_zone="B", turns_required=1)
        m2 = Movement(drone_id=1, from_zone="S", to_zone="A", turns_required=1)
        turn = TurnResult(turn_number=1, movements=[m1, m2])
        assert format_turn(turn) == "D1-A D2-B"

    def test_empty_movements(self) -> None:
        turn = TurnResult(turn_number=2, movements=[])
        assert format_turn(turn) == ""

    def test_colored_prefix(self) -> None:
        result = Movement(drone_id=1, from_zone="S", to_zone="A", turns_required=1)
        turn = TurnResult(turn_number=1, movements=[result])
        colored = format_turn(turn, color=True)
        # D1-A with drone id gold, zone foam
        assert colored.startswith("\033[38;2;246;193;119mD1\033[0m-\033[38;2;156;207;216mA\033[0m")


class TestFormatMap:
    def test_basic_structure(self) -> None:
        pmap = _parsed_map(
            nb_drones=3,
            zones=[
                _parsed_zone("base", 0, 0),
                _parsed_zone("target", 10, 10),
                _parsed_zone("mid", 5, 5, {"zone": "priority", "color": "blue"}),
            ],
            conns=[
                _parsed_conn("base", "mid", {"max_link_capacity": "3"}),
                _parsed_conn("mid", "target"),
            ],
        )
        lines = format_map(pmap)
        assert lines[0] == "nb_drones: 3"
        assert lines[1] == "start_hub: base 0 0"
        assert lines[2] == "end_hub: target 10 10"
        assert lines[3] == "hub: mid 5 5 [color=blue zone=priority]"
        assert lines[4] == "connection: base-mid [max_link_capacity=3]"
        assert lines[5] == "connection: mid-target"
        assert lines[6] == ""  # blank separator

    def test_metadata_sorted(self) -> None:
        pmap = _parsed_map(
            nb_drones=1,
            zones=[
                _parsed_zone("s", 0, 0),
                _parsed_zone("t", 1, 1),
            ],
            conns=[
                _parsed_conn("s", "t", {"max_link_capacity": "2", "foo": "bar"}),
            ],
        )
        lines = format_map(pmap)
        # metadata keys sorted alphabetically
        assert "foo=bar max_link_capacity=2" in lines[3] or "max_link_capacity=2 foo=bar" in lines[3]

    def test_colored_header(self) -> None:
        pmap = _parsed_map(
            nb_drones=2,
            zones=[
                _parsed_zone("s", 0, 0),
                _parsed_zone("t", 1, 1),
            ],
            conns=[],
        )
        lines = format_map(pmap, color=True)
        # nb_drones line colored gold
        assert "\033[38;2;246;193;119mnb_drones: 2\033[0m" in lines[0]


class TestSimulate:
    def test_single_drone_finish(self) -> None:
        graph = _graph(
            [_zone("S", start=True), _zone("A"), _zone("G", end=True)],
            [("S", "A"), ("A", "G")],
        )
        lines = list(simulate(graph, [_drone(1, "S", "G")]))
        # Final arrival turn with no movements is not printed
        assert lines == ["D1-A", "D1-G"]

    def test_restricted_zone_empty_turn(self) -> None:
        graph = _graph(
            [_zone("S", start=True), _zone("R", ZoneType.RESTRICTED), _zone("G", end=True)],
            [("S", "R"), ("R", "G")],
        )
        lines = list(simulate(graph, [_drone(1, "S", "G")]))
        # turn 1: S->R (cost 2), turn 2: empty (in transit), turn 3: R->G, turn 4: empty (arrival, not printed)
        assert lines == ["D1-R", "", "D1-G"]

    def test_deadlock_breaks(self) -> None:
        # Two drones head-on on capacity-1 link: D1 S->A, D2 A->S. Link cap 1.
        graph = _graph(
            [_zone("S", start=True), _zone("A")],
            [("S", "A")],
        )
        lines = list(simulate(graph, [_drone(1, "S", "A"), _drone(2, "A", "S")]))
        # D1 moves S->A, D2 blocked; D1 arrives, then D2 moves A->S
        assert "D1-A" in lines
        assert "D2-S" in lines

    def test_multi_drone_simultaneous(self) -> None:
        graph = _graph(
            [_zone("S", start=True), _zone("A", max_drones=2), _zone("G", end=True)],
            [("S", "A"), ("A", "G")],
            link_capacity=2,
        )
        lines = list(simulate(graph, [_drone(1, "S", "G"), _drone(2, "S", "G")]))
        # Both move S->A on turn 1
        assert "D1-A D2-A" in lines[0]


class TestPaint:
    def test_no_color_returns_plain(self) -> None:
        assert paint("hello", "gold", color=False) == "hello"

    def test_unknown_role_falls_back(self) -> None:
        assert paint("x", "nonexistent", color=True) == "x"