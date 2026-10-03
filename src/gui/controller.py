"""Simulation controller for the GUI layer.

Handles simulation state transitions: step forward/back via the
arrow keys, rewind history, and status/error toasts. Uses
pygame.time.get_ticks() for toast timing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.gui.constants import TOAST_DURATION_MS
from src.models.drone import Drone
from src.models.simulation import TurnResult
from src.simulation.engine import Simulation

if TYPE_CHECKING:
    from src.models.graph import Graph


class SimController:
    """Manages simulation state and turn progression for the GUI."""

    def __init__(self) -> None:
        """Initialize an idle controller with no attached simulation."""
        self.sim: Simulation | None = None
        self.history: list[tuple[list[Drone], int, str | None]] = []
        self.status: str | None = None
        self.status_visible_until: int | None = None

    def set_simulation(self, sim: Simulation) -> None:
        """Attach a new simulation, resetting rewind history.

        Args:
            sim: The simulation to attach.
        """
        self.sim = sim
        self.history = []

    def reset(self) -> None:
        """Clear all simulation state."""
        self.sim = None
        self.history = []
        self.status = None
        self.status_visible_until = None

    def step_forward(
        self, fleet: list[Drone] | None
    ) -> TurnResult | None:
        """Advance one turn; return TurnResult or None if no simulation
        or finished.

        Args:
            fleet: The current drone fleet, if any.

        Returns:
            The turn result, or None when unavailable or finished.
        """
        if self.sim is None or fleet is None or self.sim.finished:
            return None
        snapshot = [d.model_copy(deep=True) for d in fleet]
        self.history.append((snapshot, self.sim.state.turn, self.status))
        return self.sim.step()

    def step_back(
        self, graph: "Graph" | None
    ) -> list[Drone] | None:
        """Rewind one turn; return restored fleet or None if no
        history/graph.

        Also restores the message that was shown for the restored turn.

        Args:
            graph: The graph to rebuild the simulation with.

        Returns:
            The restored fleet, or None when unavailable.
        """
        if self.sim is None or graph is None or not self.history:
            return None
        fleet_snap, turn, message = self.history.pop()
        self.sim = Simulation(graph, fleet_snap, replan=False)
        self.sim.state.turn = turn
        self.status = message
        if message is not None:
            self.status_visible_until = (
                pygame.time.get_ticks() + TOAST_DURATION_MS
            )
        else:
            self.status_visible_until = None
        return fleet_snap

    def flash(self, message: str, error: bool) -> None:
        """Show a transient status/error message.

        Args:
            message: The message to display.
            error: Whether to style it as an error.
        """
        self.status = message
        self.status_visible_until = pygame.time.get_ticks() + TOAST_DURATION_MS

    def flash_turn(self, result: TurnResult) -> None:
        """Flash a summary of the turn's movements/conflicts.

        Args:
            result: The turn result to summarize.
        """
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
