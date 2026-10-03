"""Pure keyboard-driven map-selection menu state.

``MapMenu`` tracks the visible options, the highlighted index, and the
open/closed state of the map picker. It supports two-level navigation:
the root level lists folders, and ``descend`` drills into a folder's
maps with ``ascend`` restoring the parent level. It contains no pygame
logic so it stays unit-testable; the MapViewer renders and keys it.
"""

from __future__ import annotations


class MapMenu:
    """A selectable list of options with breadcrumb navigation."""

    def __init__(
        self, options: list[str], selected: int = 0
    ) -> None:
        """Start closed at the root level, highlighting ``options[selected]``.

        Args:
            options: The selectable options at the root level.
            selected: The index to highlight initially.
        """
        self.options = options
        self.selected = selected
        self.visible = False
        self._breadcrumb: list[tuple[list[str], int]] = []

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
        """Move the highlight by ``delta``, clamped to the list bounds.

        Args:
            delta: The signed number of rows to move.
        """
        if not self.options:
            return
        target = self.selected + delta
        self.selected = min(max(target, 0), len(self.options) - 1)

    def current(self) -> str | None:
        """Return the highlighted option, or None when empty.

        Returns:
            The highlighted map name, or None when no options exist.
        """
        if not self.options:
            return None
        return self.options[self.selected]

    def descend(self, options: list[str]) -> None:
        """Drill into a sub-list, remembering the current level.

        Args:
            options: The options of the child level to show.
        """
        self._breadcrumb.append((list(self.options), self.selected))
        self.options = list(options)
        self.selected = 0

    def ascend(self) -> bool:
        """Return to the parent level, restoring its selection.

        Returns:
            True when a parent level was restored, False at the root.
        """
        if not self._breadcrumb:
            return False
        self.options, self.selected = self._breadcrumb.pop()
        return True

    def at_root(self) -> bool:
        """Whether the menu currently shows the root (folder) level."""
        return not self._breadcrumb
