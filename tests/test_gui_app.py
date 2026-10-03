"""Headless smoke tests for the MapViewer (keyboard controls milestone).

Runs against SDL dummy drivers (see conftest.py) so no window or audio
device is needed. Exercises construction, rendering, key bindings, the
two-level folder/map picker, and resizing without pumping the real frame
loop.
"""

from __future__ import annotations

from pathlib import Path

import pygame
import pygame.event as pygame_event
import pytest

from src.gui.app import (
    HUD_HEIGHT,
    LEGEND_PADDING,
    LINK_SPACING,
    MAP_HEIGHT,
    MapViewer,
    WINDOW,
)
from src.gui.app import _in_transit_fraction
from src.gui.app import _perpendicular_offset
from src.gui.app import run
from src.models.drone import Drone
from src.models.enums import DroneStatus


VALID_MAP = (
    "nb_drones: 3\n"
    "start_hub: base 0 0\n"
    "end_hub: target 400 300\n"
    "hub: roof1 200 -100\n"
    "connection: base-roof1\n"
    "connection: roof1-target\n"
)

#: Single drone through a restricted zone: turn messages vary (a turn
#: mid-transit reports "no moves"), so rewinds can be distinguished.
RESTRICTED_MAP = (
    "nb_drones: 1\n"
    "start_hub: base 0 0\n"
    "end_hub: target 400 300\n"
    "hub: slow 200 100 [zone=restricted]\n"
    "connection: base-slow\n"
    "connection: slow-target\n"
)

#: Mirrors maps/easy/01_linear_path.txt: 2 drones, three normal hops.
LINE_MAP = (
    "nb_drones: 2\n"
    "start_hub: start 0 0\n"
    "hub: waypoint1 1 0\n"
    "hub: waypoint2 2 0\n"
    "end_hub: goal 3 0\n"
    "connection: start-waypoint1\n"
    "connection: waypoint1-waypoint2\n"
    "connection: waypoint2-goal\n"
)

#: Mirrors maps/personal/multi_lane.txt: 4 drones cross the restricted
#: ramp-tunnel link together at max_drones/max_link_capacity 4.
MULTI_LANE_MAP = (
    "nb_drones: 4\n"
    "start_hub: base 0 0\n"
    "hub: ramp 120 0 [max_drones=4]\n"
    "hub: tunnel 240 0 [zone=restricted max_drones=4]\n"
    "end_hub: goal 360 0\n"
    "connection: base-ramp [max_link_capacity=4]\n"
    "connection: ramp-tunnel [max_link_capacity=4]\n"
    "connection: tunnel-goal [max_link_capacity=4]\n"
)


def _write_map(path: Path, content: str = VALID_MAP) -> None:
    """Write a map file at the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_maps_in(tmp_path: Path, folder: str, names: list[str]) -> None:
    """Create one valid map file per name under ``folder``."""
    for name in names:
        _write_map(tmp_path / folder / name)


def _make_maps(tmp_path: Path, names: list[str]) -> None:
    """Create one valid map file per name in ``tmp_path/maps/easy/``."""
    _make_maps_in(tmp_path, "maps/easy", names)


def _make_personal_maps(tmp_path: Path, names: list[str]) -> None:
    """Create one valid map file per name in ``tmp_path/personal/``."""
    for name in names:
        _write_map(tmp_path / "personal" / name)


def _key(key: int) -> pygame_event.Event:
    """Build a KEYDOWN event for the given key."""
    return pygame_event.Event(pygame.KEYDOWN, key=key, mod=0)


class TestMapViewer:
    """Smoke tests for the pygame map viewer window state."""

    def test_renders_frame_at_window_size(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        assert viewer._render().get_size() == WINDOW

    def test_loads_starting_map_state(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        assert viewer.current_map == "maps/easy/a.txt"
        assert viewer.error is None
        assert viewer.graph is not None
        assert set(viewer.graph.zones) == {"base", "target", "roof1"}

    def test_m_key_toggles_map_menu(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt", "b.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        assert viewer.menu.visible is True
        assert viewer.menu.options == ["maps/easy"]
        assert viewer.menu.selected == 0

        viewer._handle_event(_key(pygame.K_m))
        assert viewer.menu.visible is False

    def test_arrow_keys_move_folder_selection(self, tmp_path: Path) -> None:
        _make_maps_in(tmp_path, "maps/easy", ["a.txt"])
        _make_maps_in(tmp_path, "maps/hard", ["b.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")
        viewer._handle_event(_key(pygame.K_m))

        assert viewer.menu.options == ["maps/easy", "maps/hard"]

        viewer._handle_event(_key(pygame.K_DOWN))
        assert viewer.menu.selected == 1

        viewer._handle_event(_key(pygame.K_UP))
        assert viewer.menu.selected == 0

    def test_enter_folder_descends_to_maps(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt", "b.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer.menu.visible is True
        assert viewer.menu.at_root() is False
        assert viewer.menu.options == ["maps/easy/a.txt", "maps/easy/b.txt"]
        assert viewer.current_map == "maps/easy/a.txt"

    def test_enter_loads_selected_map(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt", "b.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_RETURN))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer.current_map == "maps/easy/b.txt"
        assert viewer.menu.visible is False
        assert viewer.error is None

    def test_enter_on_current_map_is_noop(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_RETURN))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer.current_map == "maps/easy/a.txt"
        assert viewer.menu.visible is False

    def test_menu_opens_highlighting_current_folder(
        self, tmp_path: Path
    ) -> None:
        _make_maps(tmp_path, ["a.txt"])
        _make_maps_in(tmp_path, "maps/hard", ["b.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/hard/b.txt")

        viewer._handle_event(_key(pygame.K_m))

        assert viewer.menu.options == ["maps/easy", "maps/hard"]
        assert viewer.menu.selected == 1

    def test_menu_selection_keeps_current_on_parse_failure(
        self, tmp_path: Path
    ) -> None:
        _make_maps(tmp_path, ["a.txt"])
        _write_map(tmp_path / "maps" / "easy" / "bad.txt", "not a map\n")
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_RETURN))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer.current_map == "maps/easy/a.txt"
        assert viewer.error is not None
        assert "line 1" in viewer.error

    def test_escape_at_map_level_returns_to_folders(
        self, tmp_path: Path
    ) -> None:
        _make_maps(tmp_path, ["a.txt", "b.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_RETURN))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_ESCAPE))

        assert viewer.menu.visible is True
        assert viewer.menu.at_root() is True
        assert viewer.menu.options == ["maps/easy"]
        assert viewer.current_map == "maps/easy/a.txt"

    def test_escape_at_root_closes_menu(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_ESCAPE))

        assert viewer.menu.visible is False
        assert viewer.current_map == "maps/easy/a.txt"

    def test_escape_quits_when_menu_closed(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_ESCAPE))

        assert viewer.running is False

    def test_m_on_empty_dir_opens_no_menu(self, tmp_path: Path) -> None:
        viewer = MapViewer(tmp_path)

        viewer._handle_event(_key(pygame.K_m))

        assert viewer.menu.visible is False

    def test_right_advances_simulation(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")
        assert viewer.fleet is not None
        assert viewer.controller.sim is not None

        assert all(d.status == DroneStatus.WAITING for d in viewer.fleet)
        turn = viewer.controller.sim.state.turn

        viewer._handle_event(_key(pygame.K_RIGHT))

        assert viewer.current_map == "maps/easy/a.txt"
        assert viewer.running is True
        assert viewer.controller.sim.state.turn == turn + 1
        assert any(
            d.status == DroneStatus.IN_TRANSIT for d in viewer.fleet
        )

    def test_left_rewinds_simulation(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")
        assert viewer.fleet is not None

        viewer._handle_event(_key(pygame.K_RIGHT))
        assert any(
            d.status == DroneStatus.IN_TRANSIT for d in viewer.fleet
        )

        viewer._handle_event(_key(pygame.K_LEFT))
        assert all(d.status == DroneStatus.WAITING for d in viewer.fleet)

    def test_left_at_start_is_noop(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")
        assert viewer.fleet is not None

        viewer._handle_event(_key(pygame.K_LEFT))

        assert all(d.status == DroneStatus.WAITING for d in viewer.fleet)

    def test_left_restores_turn_message(self, tmp_path: Path) -> None:
        """Rewinding restores the message shown for the restored turn."""
        _write_map(tmp_path / "maps" / "easy" / "a.txt", RESTRICTED_MAP)
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_RIGHT))  # turn 1: "1 move"
        viewer._handle_event(_key(pygame.K_RIGHT))  # turn 2: "no moves"
        viewer._handle_event(_key(pygame.K_RIGHT))  # turn 3: "1 move"
        viewer._handle_event(_key(pygame.K_LEFT))  # back to turn 2

        assert viewer.controller.sim is not None
        assert viewer.controller.sim.state.turn == 2
        assert viewer.controller.status == "no moves"

        viewer._handle_event(_key(pygame.K_LEFT))  # back to turn 1
        assert viewer.controller.sim.state.turn == 1
        assert viewer.controller.status == "1 move"

    def test_rewind_to_start_clears_message(self, tmp_path: Path) -> None:
        """Rewinding to the initial turn clears the status message."""
        _write_map(tmp_path / "maps" / "easy" / "a.txt", RESTRICTED_MAP)
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_RIGHT))
        viewer._handle_event(_key(pygame.K_RIGHT))
        viewer._handle_event(_key(pygame.K_LEFT))
        viewer._handle_event(_key(pygame.K_LEFT))

        assert viewer.controller.sim is not None
        assert viewer.controller.sim.state.turn == 0
        assert viewer.controller.status is None

    def test_rewind_then_rereun_no_extra_turn(self, tmp_path: Path) -> None:
        """Rewinding and re-simulating ends at the original makespan."""
        _write_map(tmp_path / "maps" / "easy" / "a.txt", LINE_MAP)
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        def _run_to_end() -> int:
            for _ in range(30):
                if (
                    viewer.controller.sim is not None
                    and viewer.controller.sim.finished
                ):
                    break
                viewer._handle_event(_key(pygame.K_RIGHT))
            assert viewer.controller.sim is not None
            assert viewer.controller.sim.finished
            return viewer.controller.sim.state.turn

        first = _run_to_end()

        viewer._handle_event(_key(pygame.K_LEFT))
        viewer._handle_event(_key(pygame.K_LEFT))
        assert viewer.controller.sim is not None
        assert viewer.controller.sim.state.turn == first - 2

        second = _run_to_end()
        assert second == first

    def test_multi_lane_drones_stack_on_link(self, tmp_path: Path) -> None:
        """All 4 multi_lane drones sit mid-link on ramp->tunnel at once."""
        _write_map(tmp_path / "maps" / "easy" / "a.txt", MULTI_LANE_MAP)
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")
        assert viewer.fleet is not None

        for _ in range(3):
            viewer._handle_event(_key(pygame.K_RIGHT))

        transit = [
            d for d in viewer.fleet
            if d.status == DroneStatus.IN_TRANSIT
        ]
        assert len(transit) == 4
        assert all(
            d.current_zone == "ramp" and d.transit_destination == "tunnel"
            for d in transit
        )
        assert {_in_transit_fraction(d) for d in transit} == {0.5}

    def test_right_on_finished_is_noop(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")
        assert viewer.controller.sim is not None
        assert viewer.fleet is not None

        for _ in range(10):
            viewer.controller.step_forward(viewer.fleet)
            if viewer.controller.sim.finished:
                break
        assert viewer.controller.sim.finished

        turn = viewer.controller.sim.state.turn
        viewer._handle_event(_key(pygame.K_RIGHT))
        assert viewer.controller.sim.state.turn == turn

    def test_legend_shows_step_and_maps(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        assert ("<-/->", "STEP -/+") in viewer._legend_rows()
        assert ("M", "MAPS") in viewer._legend_rows()

    def test_readout_ready_at_start_then_turn(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")
        assert viewer.controller.sim is not None

        assert viewer._turn_readout() == "READY"

        viewer._handle_event(_key(pygame.K_RIGHT))
        assert viewer._turn_readout() == "TURN 1"

        viewer._handle_event(_key(pygame.K_LEFT))
        assert viewer._turn_readout() == "READY"

    def test_readout_ready_without_simulation(self, tmp_path: Path) -> None:
        viewer = MapViewer(tmp_path)

        assert viewer._turn_readout() == "READY"

    def test_positions_stay_within_map_band(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        assert viewer.positions is not None
        for _name, (px, py) in viewer.positions.items():
            assert px >= 0
            assert py <= MAP_HEIGHT

    def test_hud_has_three_stacked_rows(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")
        y0, y1, y2 = viewer._hud_row_ys()
        assert y0 < y1 < y2
        assert y0 >= MAP_HEIGHT
        line_h = viewer.legend_font.get_height()
        assert y2 + line_h <= MAP_HEIGHT + HUD_HEIGHT

    def test_hud_height_fits_three_lines(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")
        line_h = viewer.legend_font.get_height()
        assert 2 * LEGEND_PADDING + 3 * line_h + 2 * 4 + 4 <= HUD_HEIGHT

    def test_quit_event_stops_loop(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(pygame_event.Event(pygame.QUIT))

        assert viewer.running is False

    def test_toast_active_after_bad_menu_selection(
        self, tmp_path: Path
    ) -> None:
        _make_maps(tmp_path, ["a.txt"])
        _write_map(tmp_path / "maps" / "easy" / "bad.txt", "not a map\n")
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_RETURN))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer._toast_active() is True

    def test_toast_inactive_after_window_elapses(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        _write_map(tmp_path / "maps" / "easy" / "bad.txt", "not a map\n")
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_RETURN))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))
        viewer.error_visible_until = pygame.time.get_ticks() - 1

        assert viewer._toast_active() is False

    def test_successful_reload_clears_toast(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt", "b.txt"])
        _write_map(tmp_path / "maps" / "easy" / "bad.txt", "not a map\n")
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_RETURN))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))
        assert viewer._toast_active() is True

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_RETURN))
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
        _make_maps(tmp_path, ["a.txt"])
        _write_map(tmp_path / "maps" / "easy" / "bad.txt", "not a map\n")
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_RETURN))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer._render().get_size() == WINDOW

    def test_render_with_open_menu_returns_window_size(
        self, tmp_path: Path
    ) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")
        viewer._handle_event(_key(pygame.K_m))

        assert viewer._render().get_size() == WINDOW

    def test_video_resize_scales_window(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(
            pygame_event.Event(pygame.VIDEORESIZE, size=(1600, 900))
        )

        assert viewer.screen.get_size() == (1600, 900)
        assert viewer._render().get_size() == (1600, 900)

    def test_window_size_changed_resizes_screen(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(
            pygame_event.Event(pygame.WINDOWSIZECHANGED, x=800, y=500)
        )

        assert viewer.screen.get_size() == (800, 500)

    def test_resize_to_same_size_is_noop(self, tmp_path: Path) -> None:
        _make_maps(tmp_path, ["a.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")
        current = viewer.screen

        viewer._handle_event(
            pygame_event.Event(
                pygame.WINDOWSIZECHANGED, x=WINDOW[0], y=WINDOW[1]
            )
        )

        assert viewer.screen is current

    def test_map_menu_includes_personal_maps(self, tmp_path: Path) -> None:
        """Map picker shows difficulty folders and personal/."""
        _make_maps(tmp_path, ["a.txt"])
        _make_personal_maps(tmp_path, ["custom.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))

        assert viewer.menu.options == ["maps/easy", "personal"]

    def test_personal_maps_load_through_picker(self, tmp_path: Path) -> None:
        """Selecting personal/ and a map there loads it."""
        _make_maps(tmp_path, ["a.txt"])
        _make_personal_maps(tmp_path, ["custom.txt"])
        viewer = MapViewer(tmp_path, starting_map="maps/easy/a.txt")

        viewer._handle_event(_key(pygame.K_m))
        viewer._handle_event(_key(pygame.K_DOWN))
        viewer._handle_event(_key(pygame.K_RETURN))
        viewer._handle_event(_key(pygame.K_RETURN))

        assert viewer.current_map == "personal/custom.txt"
        assert viewer.menu.visible is False


class TestRun:
    """Integration tests for the entry-point root resolution."""

    def _capture_root(
        self,
        monkeypatch: pytest.MonkeyPatch,
        started: dict[str, object],
    ) -> None:
        """Stub MapViewer.run to record the viewer's root and map."""

        def _fake_run(self: MapViewer) -> None:
            started["root"] = self.maps_root
            started["map"] = self.current_map

        monkeypatch.setattr(MapViewer, "run", _fake_run)

    def test_run_resolves_root_with_nested_personal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run() finds the directory holding maps/, not maps/ itself."""
        _make_maps(tmp_path, ["a.txt"])
        map_path = tmp_path / "maps" / "easy" / "a.txt"

        started: dict[str, object] = {}
        self._capture_root(monkeypatch, started)
        run(str(map_path))

        assert started["root"] == tmp_path.resolve()
        assert started["map"] == "maps/easy/a.txt"

    def test_run_resolves_root_for_personal_in_maps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run() resolves the root for maps/personal/ map files too."""
        _make_maps(tmp_path, ["a.txt"])
        _write_map(tmp_path / "maps" / "personal" / "c.txt")
        map_path = tmp_path / "maps" / "personal" / "c.txt"

        started: dict[str, object] = {}
        self._capture_root(monkeypatch, started)
        run(str(map_path))

        assert started["root"] == tmp_path.resolve()
        assert started["map"] == "maps/personal/c.txt"

class TestInTransitFraction:
    """Unit tests for the mid-link drone progress helper."""

    def _drone(
        self,
        turns: int,
        duration: int,
        status: DroneStatus | None = None,
    ) -> Drone:
        status = status or DroneStatus.IN_TRANSIT
        return Drone(
            id=1,
            current_zone="a",
            target_zone="c",
            status=status,
            turns_in_transit=turns,
            transit_duration=duration,
            transit_destination="b",
        )

    def test_just_launched_is_at_origin(self) -> None:
        assert _in_transit_fraction(self._drone(2, 2)) == 0.0

    def test_halfway_through_restricted_hop(self) -> None:
        assert _in_transit_fraction(self._drone(1, 2)) == 0.5

    def test_single_turn_hop_at_origin(self) -> None:
        assert _in_transit_fraction(self._drone(1, 1)) == 0.0

    def test_fraction_clamped_to_one(self) -> None:
        assert _in_transit_fraction(self._drone(0, 2)) == 1.0

    def test_waiting_drone_is_none(self) -> None:
        assert (
            _in_transit_fraction(
                self._drone(0, 0, status=DroneStatus.WAITING)
            )
            is None
        )

    def test_zero_duration_in_transit_is_none(self) -> None:
        assert _in_transit_fraction(self._drone(1, 0)) is None

    def test_missing_destination_is_none(self) -> None:
        drone = Drone(
            id=1,
            current_zone="a",
            target_zone="c",
            status=DroneStatus.IN_TRANSIT,
            turns_in_transit=1,
            transit_duration=2,
        )
        assert _in_transit_fraction(drone) is None


class TestPerpendicularOffset:
    """Unit tests for the perpendicular lane-offset helper."""

    POS = {"a": (0, 0), "b": (100, 0), "c": (30, 40)}

    def test_consecutive_ranks_are_on_opposite_sides(self) -> None:
        o0 = _perpendicular_offset("a", "b", self.POS, 0)
        o1 = _perpendicular_offset("a", "b", self.POS, 1)

        assert o0 == (0, LINK_SPACING)
        assert o1 == (0, -LINK_SPACING)

    def test_magnitude_grows_with_rank(self) -> None:
        o0 = _perpendicular_offset("a", "b", self.POS, 0)
        o2 = _perpendicular_offset("a", "b", self.POS, 2)

        assert abs(o2[1]) == 2 * abs(o0[1])
        assert o2[1] > 0

    def test_direction_is_canonical_invariant(self) -> None:
        forward = _perpendicular_offset("a", "b", self.POS, 0)
        backward = _perpendicular_offset("b", "a", self.POS, 0)

        assert backward == forward

    def test_offset_is_perpendicular_to_link(self) -> None:
        offset = _perpendicular_offset("a", "c", self.POS, 0)

        # Link a->c runs along (0.6, 0.8); the offset dot it ≈ 0.
        dot = offset[0] * 0.6 + offset[1] * 0.8
        assert abs(dot) <= 1

    def test_zero_length_link_is_noop(self) -> None:
        pos = {"a": (5, 5), "b": (5, 5)}

        assert _perpendicular_offset("a", "b", pos, 0) == (0, 0)
