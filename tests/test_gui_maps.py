"""Tests for the pure GUI map helpers (map selector milestone).

Covers ``list_maps`` (discovery of ``*.map`` files) and ``load_map``
(the parse + convert + layout pipeline behind the map dropdown).
"""

from __future__ import annotations

from pathlib import Path

from src.gui.maps import list_maps, load_map


VALID_MAP = (
    "nb_drones: 3\n"
    "start_hub: base 0 0\n"
    "end_hub: target 400 300\n"
    "hub: roof1 200 -100\n"
    "connection: base-roof1\n"
    "connection: roof1-target\n"
)


def _write_map(path: Path, content: str = VALID_MAP) -> None:
    """Write a map file for the given path."""
    path.write_text(content, encoding="utf-8")


class TestListMaps:
    """Unit tests for map file discovery."""

    def test_returns_only_map_files(self, tmp_path: Path) -> None:
        _write_map(tmp_path / "a.map")
        (tmp_path / "readme.txt").write_text("", encoding="utf-8")
        (tmp_path / "notes.md").write_text("", encoding="utf-8")
        assert list_maps(tmp_path) == ["a.map"]

    def test_results_are_sorted(self, tmp_path: Path) -> None:
        for name in ["z.map", "b.map", "a.map"]:
            _write_map(tmp_path / name)
        assert list_maps(tmp_path) == ["a.map", "b.map", "z.map"]

    def test_ignores_subdirectories(self, tmp_path: Path) -> None:
        (tmp_path / "nested").mkdir()
        _write_map(tmp_path / "nested" / "inner.map")
        _write_map(tmp_path / "top.map")
        assert list_maps(tmp_path) == ["top.map"]

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        _write_map(tmp_path / "m.map")
        assert list_maps(str(tmp_path)) == ["m.map"]

    def test_returns_names_not_paths(self, tmp_path: Path) -> None:
        _write_map(tmp_path / "m.map")
        assert list_maps(tmp_path) == ["m.map"]

    def test_missing_directory(self, tmp_path: Path) -> None:
        assert list_maps(tmp_path / "does-not-exist") == []

    def test_empty_directory(self, tmp_path: Path) -> None:
        assert list_maps(tmp_path) == []


class TestLoadMap:
    """Unit tests for the load-and-layout pipeline."""

    def test_success_returns_map_state(self, tmp_path: Path) -> None:
        path = tmp_path / "map.map"
        _write_map(path)

        result, error = load_map(path)
        assert error is None
        assert result is not None
        graph, drones, positions = result

        assert set(graph.zones) == {"base", "target", "roof1"}
        assert len(drones) == 3
        assert [drone.current_zone for drone in drones] == [
            "base",
            "base",
            "base",
        ]
        assert positions.keys() == graph.zones.keys()

    def test_positions_are_pixels_within_canvas(self, tmp_path: Path) -> None:
        path = tmp_path / "map.map"
        _write_map(path)

        result, _ = load_map(path, canvas=(640, 360))
        assert result is not None
        _, _, positions = result
        for px, py in positions.values():
            assert isinstance(px, int)
            assert isinstance(py, int)
            assert 0 <= px <= 640
            assert 0 <= py <= 360

    def test_preserves_connections(self, tmp_path: Path) -> None:
        path = tmp_path / "map.map"
        _write_map(path)

        result, _ = load_map(path)
        assert result is not None
        graph, _, _ = result
        assert set(graph.connections) == {("base", "roof1"), ("roof1", "target")}

    def test_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "ghost.map"
        result, error = load_map(missing)
        assert result is None
        assert error is not None
        assert "ghost.map" in error

    def test_directory_path_is_an_error(self, tmp_path: Path) -> None:
        result, error = load_map(tmp_path)
        assert result is None
        assert error is not None

    def test_malformed_first_line(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.map"
        _write_map(path, "not a map file\n")
        result, error = load_map(path)
        assert result is None
        assert error is not None
        assert "line 1" in error

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.map"
        _write_map(path, "")
        result, error = load_map(path)
        assert result is None
        assert error is not None
        assert "line 1" in error

    def test_invalid_zone_name(self, tmp_path: Path) -> None:
        path = tmp_path / "dash.map"
        _write_map(
            path,
            "nb_drones: 1\n"
            "start_hub: bad-zone 0 0\n"
            "end_hub: end 10 10\n",
        )
        result, error = load_map(path)
        assert result is None
        assert error is not None
        assert "line 2" in error

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        path = tmp_path / "map.map"
        _write_map(path)
        result, error = load_map(str(path))
        assert error is None
        assert result is not None