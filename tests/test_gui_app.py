"""Headless smoke tests for the MapViewer (map selector milestone).

Runs against SDL dummy drivers (see conftest.py) so no window or audio
device is needed. Exercises construction, rendering, and map selection
without pumping the real frame loop.
"""

from __future__ import annotations

from pathlib import Path

import pygame
import pygame.event as pygame_event
from pygame_gui import UI_DROP_DOWN_MENU_CHANGED

from src.gui.app import MapViewer, WINDOW


VALID_MAP = (
    "nb_drones: 3\n"
    "start_hub: base 0 0\n"
    "end_hub: target 400 300\n"
    "hub: roof1 200 -100\n"
    "connection: base-roof1\n"
    "connection: roof1-target\n"
)


def _write_map(path: Path, content: str = VALID_MAP) -> None:
    """Write a map file at the given path."""
    path.write_text(content, encoding="utf-8")


def _make_maps(tmp_path: Path, names: list[str]) -> None:
    """Create one valid map file per name in ``tmp_path``."""
    for name in names:
        _write_map(tmp_path / name)


class TestMapViewer:
    """Smoke tests for the pygame map viewer window state."""

    def test_renders_frame_at_window_size(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        assert viewer._render().get_size() == WINDOW

    def test_loads_starting_map_state(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        assert viewer.current_map == "a.map"
        assert viewer.error is None
        assert viewer.graph is not None
        assert set(viewer.graph.zones) == {"base", "target", "roof1"}

    def test_dropdown_lists_available_maps(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map", "b.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        assert viewer.dropdown is not None
        labels = [
            option[0] if isinstance(option, tuple) else option
            for option in viewer.dropdown.options_list
        ]
        assert labels == ["a.map", "b.map"]

    def test_selecting_map_reloads(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map", "b.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        event = pygame_event.Event(
            UI_DROP_DOWN_MENU_CHANGED, text="b.map", ui_element=None
        )
        viewer._handle_event(event)

        assert viewer.current_map == "b.map"
        assert viewer.error is None

    def test_selecting_bad_map_keeps_current(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        (tmp_path / "bad.map").write_text("not a map\n", encoding="utf-8")
        viewer = MapViewer(tmp_path, starting_map="a.map")

        event = pygame_event.Event(
            UI_DROP_DOWN_MENU_CHANGED, text="bad.map", ui_element=None
        )
        viewer._handle_event(event)

        assert viewer.current_map == "a.map"
        assert viewer.error is not None
        assert "line 1" in viewer.error

    def test_bad_starting_map_shows_error_and_still_renders(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "bad.map").write_text("not a map\n", encoding="utf-8")
        viewer = MapViewer(tmp_path, starting_map="bad.map")

        assert viewer.current_map is None
        assert viewer.error is not None
        assert viewer._render().get_size() == WINDOW

    def test_empty_maps_dir_builds_no_dropdown(self, tmp_path: Path) -> None:
        viewer = MapViewer(tmp_path)

        assert viewer.dropdown is None
        assert viewer.error is not None

    def test_quit_event_stops_loop(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(pygame_event.Event(pygame.QUIT))

        assert viewer.running is False

    def test_escape_key_stops_loop(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(
            pygame_event.Event(
                pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0
            )
        )

        assert viewer.running is False

    def test_ignores_selection_without_dropdown(self, tmp_path: Path) -> None:
        viewer = MapViewer(tmp_path)
        event = pygame_event.Event(
            UI_DROP_DOWN_MENU_CHANGED, text="anything.map", ui_element=None
        )

        viewer._handle_event(event)

        assert viewer.current_map is None

    def test_toast_active_after_bad_selection(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        (tmp_path / "bad.map").write_text("not a map\n", encoding="utf-8")
        viewer = MapViewer(tmp_path, starting_map="a.map")

        event = pygame_event.Event(
            UI_DROP_DOWN_MENU_CHANGED, text="bad.map", ui_element=None
        )
        viewer._handle_event(event)

        assert viewer._toast_active() is True

    def test_toast_inactive_after_window_elapses(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        (tmp_path / "bad.map").write_text("not a map\n", encoding="utf-8")
        viewer = MapViewer(tmp_path, starting_map="a.map")
        event = pygame_event.Event(
            UI_DROP_DOWN_MENU_CHANGED, text="bad.map", ui_element=None
        )
        viewer._handle_event(event)

        viewer.error_visible_until = pygame.time.get_ticks() - 1

        assert viewer._toast_active() is False

    def test_successful_reload_clears_toast(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map", "b.map"])
        (tmp_path / "bad.map").write_text("not a map\n", encoding="utf-8")
        viewer = MapViewer(tmp_path, starting_map="a.map")
        bad = pygame_event.Event(
            UI_DROP_DOWN_MENU_CHANGED, text="bad.map", ui_element=None
        )
        viewer._handle_event(bad)
        assert viewer._toast_active() is True

        good = pygame_event.Event(
            UI_DROP_DOWN_MENU_CHANGED, text="b.map", ui_element=None
        )
        viewer._handle_event(good)

        assert viewer.error is None
        assert viewer._toast_active() is False

    def test_empty_dir_message_is_persistent(self, tmp_path: Path) -> None:
        viewer = MapViewer(tmp_path)

        assert viewer.error is not None
        assert viewer.error_visible_until is None
        assert viewer._toast_active() is True

    def test_render_with_toast_returns_window_size(
        self, tmp_path: Path
    ) -> None:
        _make_maps(tmp_path, ["a.map"])
        (tmp_path / "bad.map").write_text("not a map\n", encoding="utf-8")
        viewer = MapViewer(tmp_path, starting_map="a.map")
        event = pygame_event.Event(
            UI_DROP_DOWN_MENU_CHANGED, text="bad.map", ui_element=None
        )
        viewer._handle_event(event)

        assert viewer._render().get_size() == WINDOW