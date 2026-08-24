"""Simulation controller for the GUI layer.

Handles simulation state transitions: step forward/back, play/pause,
speed control, rewind history, and status/error toasts.
Uses pygame.time.get_ticks() for toast timing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.gui.constants import SPEEDS, TOAST_DURATION_MS
from src.models.drone import Drone
from src.models.simulation import TurnResult
from src.simulation.engine import Simulation

if TYPE_CHECKING:
    from src.models.graph import Graph


class SimController:
    """Manages simulation state and turn progression for the GUI."""

    def __init__(self) -> None:
        self.sim: Simulation | None = None
        self.history: list[tuple[list[Drone], int]] = []
        self.playing = False
        self._accum = 0.0
        self.speed_index = 1
        self.status: str | None = None
        self.status_visible_until: int | None = None

    def set_simulation(self, sim: Simulation) -> None:
        """Attach a new simulation, resetting history and playback state."""
        self.sim = sim
        self.history = []
        self.playing = False
        self._accum = 0.0

    def reset(self) -> None:
        """Clear all simulation state."""
        self.sim = None
        self.history = []
        self.playing = False
        self._accum = 0.0
        self.status = None
        self.status_visible_until = None

    def step_forward(
        self, fleet: list[Drone] | None
    ) -> TurnResult | None:
        """Advance one turn; return TurnResult or None if no simulation
        or finished."""
        if self.sim is None or fleet is None or self.sim.finished:
            return None
        snapshot = [d.model_copy(deep=True) for d in fleet]
        self.history.append((snapshot, self.sim.state.turn))
        return self.sim.step()

    def step_back(
        self, graph: "Graph" | None
    ) -> list[Drone] | None:
        """Rewind one turn; return restored fleet or None if no
        history/graph."""
        if self.sim is None or graph is None or not self.history:
            return None
        fleet_snap, turn = self.history.pop()
        self.sim = Simulation(graph, fleet_snap)
        self.sim.state.turn = turn
        self.playing = False
        self._accum = 0.0
        return fleet_snap

    def toggle_play(self, fleet: list[Drone] | None) -> None:
        """Pause auto-play, or single-step while paused."""
        if self.sim is None or fleet is None:
            self.flash("Load a map first", error=False)
            return
        if self.sim.finished:
            self.flash("Simulation complete", error=False)
            return
        if self.playing:
            self.playing = False
            self.flash("Paused", error=False)
        else:
            result = self.step_forward(fleet)
            if result is not None:
                self.flash_turn(result)

    def speed_up(self) -> None:
        """Cycle to next faster speed and start auto-play."""
        self.speed_index = (self.speed_index + 1) % len(SPEEDS)
        if self.sim is not None and not self.sim.finished:
            self.playing = True
            self._accum = 0.0
            self.flash(f"Playing {SPEEDS[self.speed_index]:g}x", error=False)

    def speed_down(self) -> None:
        """Cycle to next slower speed and start auto-play."""
        self.speed_index = (self.speed_index - 1) % len(SPEEDS)
        if self.sim is not None and not self.sim.finished:
            self.playing = True
            self._accum = 0.0
            self.flash(f"Playing {SPEEDS[self.speed_index]:g}x", error=False)

    def auto_step(self, dt_ms: int, fleet: list[Drone] | None) -> None:
        """Advance simulation if playing and interval elapsed."""
        if not self.playing or self.sim is None or self.sim.finished:
            return
        if fleet is None:
            return
        self._accum += dt_ms / 1000.0
        interval = 1.0 / SPEEDS[self.speed_index]
        if self._accum >= interval:
            self._accum -= interval
            result = self.step_forward(fleet)
            if result is not None:
                self.flash_turn(result)
            if self.sim is not None and self.sim.finished:
                self.playing = False
                self.flash("Simulation complete", error=False)

    def flash(self, message: str, error: bool) -> None:
        """Show a transient status/error message."""
        self.status = message
        self.status_visible_until = pygame.time.get_ticks() + TOAST_DURATION_MS

    def flash_turn(self, result: TurnResult) -> None:
        """Flash a summary of the turn's movements/conflicts."""
        parts: list[str] = []
        if result.movements:
            parts.append(f"{len(result.movements)} move")
        if result.conflicts:
            parts.append(f"{len(result.conflicts)} conflict")
        if not parts:
            parts.append("no moves")
        self.flash(", ".join(parts), error=bool(result.conflicts))

    def prune_status(self) -> None:
        """Clear status/error messages whose display window has elapsed."""
        if (
            self.status is not None
            and self.status_visible_until is not None
            and pygame.time.get_ticks() >= self.status_visible_until
        ):
            self.status = None
            self.status_visible_until = None
