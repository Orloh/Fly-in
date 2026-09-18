"""Headless test configuration for the pygame GUI.

Sets SDL dummy drivers before any pygame module initializes a display,
so GUI tests can run without a video device or audio output.
"""

import os

import pytest

from collections.abc import Callable
from src.models import Graph, Zone, Connection, ZoneType, Drone
from src.models.graph_utils import canonical_key

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


@pytest.fixture
def simple_graph() -> Graph:
    """S -> A -> G (all normal, cap 1). Single drone makespan = 3."""
    zones = {
        "S": Zone(name="S", x=0, y=0, zone_type=ZoneType.NORMAL,
                  is_start_hub=True, max_drones=1),
        "A": Zone(name="A", x=1, y=0, zone_type=ZoneType.NORMAL, max_drones=1),
        "G": Zone(name="G", x=2, y=0, zone_type=ZoneType.NORMAL,
                  is_end_hub=True, max_drones=1),
    }
    connections = {
        canonical_key("S", "A"): Connection(
            zone_a="S", zone_b="A", max_link_capacity=1),
        canonical_key("A", "G"): Connection(
            zone_a="A", zone_b="G", max_link_capacity=1),
    }
    return Graph(zones=zones, connections=connections)


@pytest.fixture
def restricted_graph() -> Graph:
    """S -> R -> G (R restricted, cost 2). Single drone makespan = 4."""
    zones = {
        "S": Zone(name="S", x=0, y=0, zone_type=ZoneType.NORMAL,
                  is_start_hub=True, max_drones=1),
        "R": Zone(name="R", x=1, y=0,
                  zone_type=ZoneType.RESTRICTED, max_drones=1),
        "G": Zone(name="G", x=2, y=0, zone_type=ZoneType.NORMAL,
                  is_end_hub=True, max_drones=1),
    }
    connections = {
        canonical_key("S", "R"): Connection(
            zone_a="S", zone_b="R", max_link_capacity=1),
        canonical_key("R", "G"): Connection(
            zone_a="R", zone_b="G", max_link_capacity=1),
    }
    return Graph(zones=zones, connections=connections)


@pytest.fixture
def split_graph() -> Graph:
    """Two disjoint routes S->A->G and S->B->G. 2 drones can arrive T3."""
    zones = {
        "S": Zone(name="S", x=0, y=0, zone_type=ZoneType.NORMAL,
                  is_start_hub=True, max_drones=1),
        "A": Zone(name="A", x=1, y=1,
                  zone_type=ZoneType.NORMAL, max_drones=1),
        "B": Zone(name="B", x=1, y=-1,
                  zone_type=ZoneType.NORMAL, max_drones=1),
        "G": Zone(name="G", x=2, y=0, zone_type=ZoneType.NORMAL,
                  is_end_hub=True, max_drones=1),
    }
    connections = {
        canonical_key("S", "A"): Connection(
            zone_a="S", zone_b="A", max_link_capacity=1),
        canonical_key("A", "G"): Connection(
            zone_a="A", zone_b="G", max_link_capacity=1),
        canonical_key("S", "B"): Connection(
            zone_a="S", zone_b="B", max_link_capacity=1),
        canonical_key("B", "G"): Connection(
            zone_a="B", zone_b="G", max_link_capacity=1),
    }
    return Graph(zones=zones, connections=connections)


@pytest.fixture
def head_on_graph() -> Graph:
    """A <-> B (link cap 1). Head-on collision test, makespan = 3."""
    zones = {
        "A": Zone(name="A", x=0, y=0, zone_type=ZoneType.NORMAL, max_drones=1),
        "B": Zone(name="B", x=1, y=0, zone_type=ZoneType.NORMAL, max_drones=1),
    }
    connections = {
        canonical_key("A", "B"): Connection(
            zone_a="A", zone_b="B", max_link_capacity=1),
    }
    return Graph(zones=zones, connections=connections)


@pytest.fixture
def bottleneck_graph() -> Graph:
    """Synthetic bottleneck: 8 drones, 2 restricted chokes (cap 1),
    merge at wide (cap 4)."""
    zones = {
        "base": Zone(name="base", x=0, y=0, zone_type=ZoneType.NORMAL,
                     is_start_hub=True, max_drones=1),
        "choke1": Zone(name="choke1", x=1, y=-1,
                       zone_type=ZoneType.RESTRICTED, max_drones=1),
        "choke2": Zone(name="choke2", x=1, y=1,
                       zone_type=ZoneType.RESTRICTED, max_drones=1),
        "wide": Zone(name="wide", x=2, y=0, zone_type=ZoneType.NORMAL,
                     max_drones=4),
        "target": Zone(name="target", x=3, y=0, zone_type=ZoneType.NORMAL,
                       is_end_hub=True, max_drones=1),
    }
    connections = {
        canonical_key("base", "choke1"): Connection(
            zone_a="base", zone_b="choke1", max_link_capacity=1),
        canonical_key("base", "choke2"): Connection(
            zone_a="base", zone_b="choke2", max_link_capacity=1),
        canonical_key("choke1", "wide"): Connection(
            zone_a="choke1", zone_b="wide", max_link_capacity=2),
        canonical_key("choke2", "wide"): Connection(
            zone_a="choke2", zone_b="wide", max_link_capacity=2),
        canonical_key("wide", "target"): Connection(
            zone_a="wide", zone_b="target", max_link_capacity=4),
    }
    return Graph(zones=zones, connections=connections)


@pytest.fixture
def finite_goal_graph() -> Graph:
    """Goal is finite-capacity zone (not end_hub). Tests post-arrival
    occupancy."""
    zones = {
        "S": Zone(name="S", x=0, y=0, zone_type=ZoneType.NORMAL,
                  is_start_hub=True, max_drones=1),
        "G": Zone(name="G", x=1, y=0, zone_type=ZoneType.NORMAL, max_drones=1),
    }
    connections = {
        canonical_key("S", "G"): Connection(
            zone_a="S", zone_b="G", max_link_capacity=1),
    }
    return Graph(zones=zones, connections=connections)


@pytest.fixture
def disconnected_graph() -> Graph:
    """S isolated from target (no connection). Tests unreachable handling."""
    zones = {
        "S": Zone(name="S", x=0, y=0, zone_type=ZoneType.NORMAL,
                  is_start_hub=True, max_drones=1),
        "unreachable": Zone(name="unreachable", x=1, y=0,
                            zone_type=ZoneType.NORMAL, max_drones=1),
    }
    connections: dict[tuple[str, str], Connection] = {}
    return Graph(zones=zones, connections=connections)


@pytest.fixture
def restricted_alternative_graph() -> Graph:
    """S -> A(normal) -> G AND S -> R(restricted) -> G.
    Cheaper route is S-A-G (cost 2) vs S-R-G (cost 3)."""
    zones = {
        "S": Zone(name="S", x=0, y=0, zone_type=ZoneType.NORMAL,
                  is_start_hub=True, max_drones=1),
        "A": Zone(name="A", x=1, y=1, zone_type=ZoneType.NORMAL, max_drones=1),
        "R": Zone(name="R", x=1, y=-1, zone_type=ZoneType.RESTRICTED,
                  max_drones=1),
        "G": Zone(name="G", x=2, y=0, zone_type=ZoneType.NORMAL,
                  is_end_hub=True, max_drones=1),
    }
    connections = {
        canonical_key("S", "A"): Connection(
            zone_a="S", zone_b="A", max_link_capacity=1),
        canonical_key("A", "G"): Connection(
            zone_a="A", zone_b="G", max_link_capacity=1),
        canonical_key("S", "R"): Connection(
            zone_a="S", zone_b="R", max_link_capacity=1),
        canonical_key("R", "G"): Connection(
            zone_a="R", zone_b="G", max_link_capacity=1),
    }
    return Graph(zones=zones, connections=connections)


@pytest.fixture
def blocked_zone_graph() -> Graph:
    """S -> A(blocked) -> G AND S -> B(normal) -> G.
    Only S-B-G is viable."""
    zones = {
        "S": Zone(name="S", x=0, y=0, zone_type=ZoneType.NORMAL,
                  is_start_hub=True, max_drones=1),
        "A": Zone(name="A", x=1, y=1, zone_type=ZoneType.BLOCKED,
                  max_drones=1),
        "B": Zone(name="B", x=1, y=-1, zone_type=ZoneType.NORMAL,
                  max_drones=1),
        "G": Zone(name="G", x=2, y=0, zone_type=ZoneType.NORMAL,
                  is_end_hub=True, max_drones=1),
    }
    connections = {
        canonical_key("S", "A"): Connection(
            zone_a="S", zone_b="A", max_link_capacity=1),
        canonical_key("A", "G"): Connection(
            zone_a="A", zone_b="G", max_link_capacity=1),
        canonical_key("S", "B"): Connection(
            zone_a="S", zone_b="B", max_link_capacity=1),
        canonical_key("B", "G"): Connection(
            zone_a="B", zone_b="G", max_link_capacity=1),
    }
    return Graph(zones=zones, connections=connections)


@pytest.fixture
def priority_tie_graph() -> Graph:
    """S -> P(priority) -> G AND S -> N(normal) -> G.
    Both cost 2, but P route has priority zone."""
    zones = {
        "S": Zone(name="S", x=0, y=0, zone_type=ZoneType.NORMAL,
                  is_start_hub=True, max_drones=1),
        "P": Zone(name="P", x=1, y=1, zone_type=ZoneType.PRIORITY,
                  max_drones=1),
        "N": Zone(name="N", x=1, y=-1, zone_type=ZoneType.NORMAL,
                  max_drones=1),
        "G": Zone(name="G", x=2, y=0, zone_type=ZoneType.NORMAL,
                  is_end_hub=True, max_drones=1),
    }
    connections = {
        canonical_key("S", "P"): Connection(
            zone_a="S", zone_b="P", max_link_capacity=1),
        canonical_key("P", "G"): Connection(
            zone_a="P", zone_b="G", max_link_capacity=1),
        canonical_key("S", "N"): Connection(
            zone_a="S", zone_b="N", max_link_capacity=1),
        canonical_key("N", "G"): Connection(
            zone_a="N", zone_b="G", max_link_capacity=1),
    }
    return Graph(zones=zones, connections=connections)


@pytest.fixture
def priority_longer_graph() -> Graph:
    """S -> P(priority) -> X -> G (cost 3, 1 priority)
    AND S -> N(normal) -> G (cost 2, 0 priority).
    Shorter normal route should win over longer priority route."""
    zones = {
        "S": Zone(name="S", x=0, y=0, zone_type=ZoneType.NORMAL,
                  is_start_hub=True, max_drones=1),
        "P": Zone(name="P", x=1, y=1, zone_type=ZoneType.PRIORITY,
                  max_drones=1),
        "X": Zone(name="X", x=2, y=1, zone_type=ZoneType.NORMAL,
                  max_drones=1),
        "N": Zone(name="N", x=1, y=-1, zone_type=ZoneType.NORMAL,
                  max_drones=1),
        "G": Zone(name="G", x=2, y=0, zone_type=ZoneType.NORMAL,
                  is_end_hub=True, max_drones=1),
    }
    connections = {
        canonical_key("S", "P"): Connection(
            zone_a="S", zone_b="P", max_link_capacity=1),
        canonical_key("P", "X"): Connection(
            zone_a="P", zone_b="X", max_link_capacity=1),
        canonical_key("X", "G"): Connection(
            zone_a="X", zone_b="G", max_link_capacity=1),
        canonical_key("S", "N"): Connection(
            zone_a="S", zone_b="N", max_link_capacity=1),
        canonical_key("N", "G"): Connection(
            zone_a="N", zone_b="G", max_link_capacity=1),
    }
    return Graph(zones=zones, connections=connections)


@pytest.fixture
def drones_at_start() -> Callable[[int, str, str], list[Drone]]:
    """Factory: n drones at start_zone targeting goal_zone."""
    def _make(n: int, start: str = "S", goal: str = "G") -> list[Drone]:
        return [
            Drone(id=i, current_zone=start, target_zone=goal)
            for i in range(1, n + 1)
        ]
    return _make
