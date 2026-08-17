"""Unit tests for the keyboard-driven map menu state machine."""

from __future__ import annotations

from src.gui.menu import MapMenu


class TestMapMenu:
    """MapMenu selection and visibility behavior."""

    def test_starts_closed_with_first_option(self) -> None:
        menu = MapMenu(["a.map", "b.map"])

        assert menu.visible is False
        assert menu.selected == 0
        assert menu.current() == "a.map"

    def test_toggle_flips_visibility(self) -> None:
        menu = MapMenu(["a.map"])

        menu.toggle()
        assert menu.visible is True

        menu.toggle()
        assert menu.visible is False

    def test_open_and_close(self) -> None:
        menu = MapMenu(["a.map"])

        menu.open()
        assert menu.visible is True

        menu.close()
        assert menu.visible is False

    def test_move_clamps_at_bottom(self) -> None:
        menu = MapMenu(["a.map", "b.map", "c.map"])

        menu.move(-5)

        assert menu.selected == 0

    def test_move_clamps_at_top(self) -> None:
        menu = MapMenu(["a.map", "b.map", "c.map"])

        menu.move(5)

        assert menu.selected == 2

    def test_move_steps_through_options(self) -> None:
        menu = MapMenu(["a.map", "b.map", "c.map"])

        menu.move(1)
        assert menu.selected == 1
        assert menu.current() == "b.map"

        menu.move(-1)
        assert menu.selected == 0

    def test_move_on_empty_list_is_noop(self) -> None:
        menu = MapMenu([])

        menu.move(1)

        assert menu.selected == 0
        assert menu.current() is None

    def test_current_on_empty_list_is_none(self) -> None:
        menu = MapMenu([])

        assert menu.current() is None

    def test_starts_highlighting_given_index(self) -> None:
        menu = MapMenu(["a.map", "b.map", "c.map"], selected=2)

        assert menu.selected == 2
        assert menu.current() == "c.map"
