"""Pure keyboard-driven map-selection menu state.

``MapMenu`` tracks the visible options, the highlighted index, and the
open/closed state of the map picker. It contains no pygame logic so it
stays unit-testable; the MapViewer renders and keys it.
"""

from __future__ import annotations


class MapMenu:
    """A selectable list of map names with open/closed state."""

    def __init__(
        self, options: list[str], selected: int = 0
    ) -> None:
        """Start closed, highlighting ``options[selected]``."""
        self.options = options
        self.selected = selected
        self.visible = False

    def toggle(self) -> None:
        """Flip the menu between open and closed."""
        self.visible = not self.visible

    def open(self) -> None:
        """Show the menu."""
        self.visible = True

    def close(self) -> None:
        """Hide the menu."""
        self.visible = False

    def move(self, delta: int) -> None:
        """Move the highlight by ``delta``, clamped to the list bounds."""
        if not self.options:
            return
        target = self.selected + delta
        self.selected = min(max(target, 0), len(self.options) - 1)

    def current(self) -> str | None:
        """Return the highlighted option, or None when empty."""
        if not self.options:
            return None
        return self.options[self.selected]
