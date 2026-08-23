"""Headless smoke tests for the MapViewer (keyboard controls milestone).

Runs against SDL dummy drivers (see conftest.py) so no window or audio
device is needed. Exercises construction, rendering, key bindings, the
map menu, and resizing without pumping the real frame loop.
"""

from __future__ import annotations

from pathlib import Path

import pygame
import pygame.event as pygame_event

from src.gui.app import MAP_HEIGHT, SPEEDS, MapViewer, WINDOW
from src.models.enums import DroneStatus


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


def _key(key: int) -> pygame_event.Event:
    """Build a KEYDOWN event for the given key."""
    return pygame_event.Event(pygame.KEYDOWN, key=key, mod=0)


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

    def test_m_key_toggles_map_menu(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map", "b.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_m))
        assert viewer.menu.visible is True
        assert viewer.menu.options == ["a.map", "b.map"]
        assert viewer.menu.selected == 0

        viewer._handle_event(_key(pygame.K_m))
        assert viewer.menu.visible is False

    def test_arrow_keys_move_menu_selection(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map", "b.map", "c.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")
        viewer._handle_event(_key(pygame.K_m))

        viewer._handle_event(_key(pygame.K_DOWN))
        assert viewer.menu.selected == 1

        viewer._handle_event(_key(pygame.K_UP))
        assert viewer.menu.selected == 0

    def test_enter_loads_selected_map(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map", "b.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer.current_map == "b.map"
        assert viewer.menu.visible is False
        assert viewer.error is None

    def test_enter_on_current_map_is_noop(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer.current_map == "a.map"
        assert viewer.menu.visible is False

    def test_menu_selection_keeps_current_on_parse_failure(
        self, tmp_path: Path
    ) -> None:
        _make_maps(tmp_path, ["a.map"])
        (tmp_path / "bad.map").write_text("not a map\n", encoding="utf-8")
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer.current_map == "a.map"
        assert viewer.error is not None
        assert "line 1" in viewer.error

    def test_escape_closes_menu_without_loading(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map", "b.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_ESCAPE))

        assert viewer.menu.visible is False
        assert viewer.current_map == "a.map"

    def test_escape_quits_when_menu_closed(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_ESCAPE))

        assert viewer.running is False

    def test_m_on_empty_dir_opens_no_menu(self, tmp_path: Path) -> None:
        viewer = MapViewer(tmp_path)

        viewer._handle_event(_key(pygame.K_m))

        assert viewer.menu.visible is False

    def test_speed_keys_cycle_with_wrap(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        assert SPEEDS[viewer.speed_index] == 1.0

        viewer._handle_event(_key(pygame.K_PLUS))
        assert SPEEDS[viewer.speed_index] == 2.0
        viewer._handle_event(_key(pygame.K_PLUS))
        assert SPEEDS[viewer.speed_index] == 4.0
        viewer._handle_event(_key(pygame.K_PLUS))
        assert SPEEDS[viewer.speed_index] == 0.5
        viewer._handle_event(_key(pygame.K_MINUS))
        assert SPEEDS[viewer.speed_index] == 4.0

    def test_equals_key_acts_as_plus(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_EQUALS))

        assert SPEEDS[viewer.speed_index] == 2.0

    def test_space_advances_simulation(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        assert all(d.status == DroneStatus.WAITING for d in viewer.fleet)

        viewer._handle_event(_key(pygame.K_SPACE))

        assert viewer.current_map == "a.map"
        assert viewer.running is True
        assert any(
            d.status == DroneStatus.IN_TRANSIT for d in viewer.fleet
        )

    def test_backspace_rewinds_simulation(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_SPACE))
        assert any(
            d.status == DroneStatus.IN_TRANSIT for d in viewer.fleet
        )

        viewer._handle_event(_key(pygame.K_BACKSPACE))
        assert all(d.status == DroneStatus.WAITING for d in viewer.fleet)

    def test_space_on_finished_is_noop(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        for _ in range(10):
            viewer._step_forward()
            if viewer.sim.finished:
                break
        assert viewer.sim.finished

        turn = viewer.sim.state.turn
        viewer._handle_event(_key(pygame.K_SPACE))
        assert viewer.sim.state.turn == turn

    def test_speed_keys_start_autoplay(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_PLUS))
        assert viewer.playing is True
        assert SPEEDS[viewer.speed_index] == 2.0

    def test_space_toggles_pause(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._speed_up()
        assert viewer.playing is True

        viewer._handle_event(_key(pygame.K_SPACE))
        assert viewer.playing is False

    def test_auto_step_advances_while_playing(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")
        viewer.playing = True
        viewer.speed_index = 0  # 0.5x -> 2s interval

        before = viewer.sim.state.turn
        viewer._auto_step(2500)
        assert viewer.sim.state.turn == before + 1

        turn = viewer.sim.state.turn
        viewer._auto_step(500)
        assert viewer.sim.state.turn == turn

    def test_positions_stay_within_map_band(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        assert viewer.positions is not None
        for _name, (px, py) in viewer.positions.items():
            assert px >= 0
            assert py <= MAP_HEIGHT

    def test_legend_shows_live_speed(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        assert ("+/-", "SPEED 1x") in viewer._legend_rows()

        viewer._speed_up()
        assert ("+/-", "SPEED 2x") in viewer._legend_rows()

    def test_quit_event_stops_loop(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(pygame_event.Event(pygame.QUIT))

        assert viewer.running is False

    def test_toast_active_after_bad_menu_selection(
        self, tmp_path: Path
    ) -> None:
        _make_maps(tmp_path, ["a.map"])
        (tmp_path / "bad.map").write_text("not a map\n", encoding="utf-8")
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer._toast_active() is True

    def test_toast_inactive_after_window_elapses(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        (tmp_path / "bad.map").write_text("not a map\n", encoding="utf-8")
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))
        viewer.error_visible_until = pygame.time.get_ticks() - 1

        assert viewer._toast_active() is False

    def test_successful_reload_clears_toast(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map", "b.map"])
        (tmp_path / "bad.map").write_text("not a map\n", encoding="utf-8")
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))
        assert viewer._toast_active() is True

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))

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

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer._render().get_size() == WINDOW

    def test_render_with_open_menu_returns_window_size(
        self, tmp_path: Path
    ) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")
        viewer._handle_event(_key(pygame.K_m))

        assert viewer._render().get_size() == WINDOW

    def test_video_resize_scales_window(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(
            pygame_event.Event(pygame.VIDEORESIZE, size=(1600, 900))
        )

        assert viewer.screen.get_size() == (1600, 900)
        assert viewer._render().get_size() == (1600, 900)

    def test_window_size_changed_resizes_screen(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")

        viewer._handle_event(
            pygame_event.Event(pygame.WINDOWSIZECHANGED, x=800, y=500)
        )

        assert viewer.screen.get_size() == (800, 500)

    def test_resize_to_same_size_is_noop(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.map"])
        viewer = MapViewer(tmp_path, starting_map="a.map")
        current = viewer.screen

        viewer._handle_event(
            pygame_event.Event(
                pygame.WINDOWSIZECHANGED, x=WINDOW[0], y=WINDOW[1]
            )
        )

        assert viewer.screen is current