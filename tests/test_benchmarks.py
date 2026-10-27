"""Benchmark conformance tests against the subject VII.7 targets.

Each provided tier map must solve at or under its reference target turn
count, locking in the measured performance so solver regressions
surface.
"""

from __future__ import annotations

import pathlib

import pytest

from src.parser import build_graph, parse_map
from src.simulation.engine import Simulation

_MAPS = pathlib.Path(__file__).resolve().parents[1] / "maps"

#: Subject VII.7 reference targets (turns) per provided map.
TARGETS = {
    "easy/01_linear_path.txt": 6,
    "easy/02_simple_fork.txt": 8,
    "easy/03_basic_capacity.txt": 6,
    "medium/01_dead_end_trap.txt": 12,
    "medium/02_circular_loop.txt": 15,
    "medium/03_priority_puzzle.txt": 12,
    "hard/01_maze_nightmare.txt": 30,
    "hard/02_capacity_hell.txt": 35,
    "hard/03_ultimate_challenge.txt": 45,
    "challenger/01_the_impossible_dream.txt": 45,
}


def _makespan(relative: str) -> int:
    """The makespan of the tier map at ``relative``."""
    path = _MAPS / relative
    parsed = parse_map(str(path))
    graph, fleet = build_graph(parsed)
    return Simulation(graph, fleet).schedule.makespan


@pytest.mark.parametrize("relative,target", sorted(TARGETS.items()))
def test_makespan_meets_target(relative: str, target: int) -> None:
    """The map solves within its VII.7 reference target."""
    makespan = _makespan(relative)
    assert makespan <= target


def test_circular_loop_meets_target() -> None:
    """``circular_loop`` meets the subject's 15-turn target.

    Every drone must cross the cap-1 two-turn link loop_b-exit_point
    one at a time. The sixth drone still reaches the goal on turn 15,
    so the target is achievable on this topology.
    """
    assert _makespan("medium/02_circular_loop.txt") == 15


def test_impossible_dream_beats_reference() -> None:
    """``impossible_dream`` solves within the 45-turn reference record."""
    assert _makespan(
        "challenger/01_the_impossible_dream.txt"
    ) <= 45
