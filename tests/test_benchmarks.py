"""Benchmark conformance tests against the subject VII.7 targets.

Each provided tier map must solve at or under its reference target turn
count, locking in the measured performance so solver regressions
surface. ``circular_loop`` is the exception: its cap-1 two-turn link
makes 16 provably optimal (see ``test_circular_loop_is_optimal``), so
its expected value here is the documented floor rather than the
unachievable 15.
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
    "medium/02_circular_loop.txt": 16,  # subject: 15; 16 is the floor
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


def test_circular_loop_is_optimal() -> None:
    """``circular_loop``'s 16 is optimal, not merely near its target.

    Every drone must cross the cap-1 two-turn link loop_b-exit_point
    one at a time: drone i starts that transit at turn 2i+3, lands at
    exit_point at turn 2i+5, and needs one more turn to reach the goal.
    The sixth of six drones therefore arrives at turn 16, so no
    schedule can do better on this topology.
    """
    assert _makespan("medium/02_circular_loop.txt") == 16


def test_impossible_dream_beats_reference() -> None:
    """``impossible_dream`` solves within the 45-turn reference record."""
    assert _makespan(
        "challenger/01_the_impossible_dream.txt"
    ) <= 45