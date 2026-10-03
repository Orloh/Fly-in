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


class TestMapMenuNavigation:
    """MapMenu two-level folder/map navigation."""

    def test_descend_swaps_options_and_resets_selection(self) -> None:
        menu = MapMenu(["maps/easy", "personal"], selected=1)
        menu.descend(["maps/easy/a.txt", "maps/easy/b.txt"])

        assert menu.options == ["maps/easy/a.txt", "maps/easy/b.txt"]
        assert menu.selected == 0
        assert menu.at_root() is False
        assert menu.current() == "maps/easy/a.txt"

    def test_ascend_restores_parent_options_and_selection(self) -> None:
        menu = MapMenu(["maps/easy", "personal"], selected=1)
        menu.descend(["maps/easy/a.txt"])

        assert menu.ascend() is True
        assert menu.options == ["maps/easy", "personal"]
        assert menu.selected == 1
        assert menu.at_root() is True

    def test_ascend_at_root_returns_false(self) -> None:
        menu = MapMenu(["maps/easy"])

        assert menu.ascend() is False
        assert menu.options == ["maps/easy"]

    def test_at_root_true_without_breadcrumb(self) -> None:
        menu = MapMenu(["maps/easy"])

        assert menu.at_root() is True

    def test_multiple_levels_ascend_in_order(self) -> None:
        menu = MapMenu(["maps/easy"])
        menu.descend(["maps/easy/a.txt"])
        menu.selected = 1
        menu.descend(["maps/easy/a.txt"])
        menu.move(-1)

        assert menu.ascend() is True
        assert menu.options == ["maps/easy/a.txt"]
        assert menu.selected == 1
        assert menu.ascend() is True
        assert menu.options == ["maps/easy"]
        assert menu.ascend() is False

    def test_descend_keeps_a_copy_of_parent_options(self) -> None:
        menu = MapMenu(["maps/easy"])
        menu.descend(["maps/easy/a.txt"])
        menu.options[0] = "changed.txt"

        assert menu.ascend() is True
        assert menu.options == ["maps/easy"]
