"""Tests for the pure GUI map helpers (map picker milestone).

Covers ``list_maps`` (discovery of ``*.txt`` files recursively from maps_root)
and ``load_map`` (the parse + convert + layout pipeline behind the map picker).
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestListMaps:
    """Unit tests for map file discovery."""

    def test_returns_txt_files_recursively(self, tmp_path: Path) -> None:
        """Discover .txt files in maps/ and personal/ subdirectories."""
        maps_root = tmp_path
        _write_map(maps_root / "maps" / "easy" / "a.txt")
        _write_map(maps_root / "maps" / "hard" / "b.txt")
        _write_map(maps_root / "personal" / "c.txt")
        (maps_root / "readme.md").write_text("", encoding="utf-8")

        result = list_maps(maps_root)

        assert result == [
            "maps/easy/a.txt",
            "maps/hard/b.txt",
            "personal/c.txt",
        ]

    def test_results_are_sorted(self, tmp_path: Path) -> None:
        """Maps are sorted by relative path."""
        maps_root = tmp_path
        _write_map(maps_root / "maps" / "z.txt")
        _write_map(maps_root / "personal" / "a.txt")
        _write_map(maps_root / "maps" / "easy" / "b.txt")

        assert list_maps(maps_root) == [
            "maps/easy/b.txt",
            "maps/z.txt",
            "personal/a.txt",
        ]

    def test_ignores_non_txt_files(self, tmp_path: Path) -> None:
        """Only .txt files are returned."""
        maps_root = tmp_path
        _write_map(maps_root / "maps" / "a.txt")
        (maps_root / "maps" / "b.map").write_text("", encoding="utf-8")
        (maps_root / "maps" / "c.md").write_text("", encoding="utf-8")

        assert list_maps(maps_root) == ["maps/a.txt"]

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Function accepts string paths."""
        maps_root = tmp_path
        _write_map(maps_root / "maps" / "m.txt")
        assert list_maps(str(maps_root)) == ["maps/m.txt"]

    def test_missing_directory(self, tmp_path: Path) -> None:
        """Non-existent root returns empty list."""
        assert list_maps(tmp_path / "does-not-exist") == []

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Root with no maps/ or personal/ returns empty list."""
        assert list_maps(tmp_path) == []

    def test_maps_dir_only(self, tmp_path: Path) -> None:
        """Works when only maps/ directory exists."""
        maps_root = tmp_path
        _write_map(maps_root / "maps" / "a.txt")
        assert list_maps(maps_root) == ["maps/a.txt"]

    def test_personal_dir_only(self, tmp_path: Path) -> None:
        """Works when only personal/ directory exists."""
        maps_root = tmp_path
        _write_map(maps_root / "personal" / "a.txt")
        assert list_maps(maps_root) == ["personal/a.txt"]


class TestLoadMap:
    """Unit tests for the load-and-layout pipeline."""

    def test_success_returns_map_state(self, tmp_path: Path) -> None:
        """Load a map by relative path from maps_root."""
        maps_root = tmp_path
        _write_map(maps_root / "maps" / "map.txt")

        result, error = load_map(maps_root, "maps/map.txt")
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
        """Positions are integer pixels within the canvas bounds."""
        maps_root = tmp_path
        _write_map(maps_root / "maps" / "map.txt")

        result, _ = load_map(maps_root, "maps/map.txt", canvas=(640, 360))
        assert result is not None
        _, _, positions = result
        for px, py in positions.values():
            assert isinstance(px, int)
            assert isinstance(py, int)
            assert 0 <= px <= 640
            assert 0 <= py <= 360

    def test_preserves_connections(self, tmp_path: Path) -> None:
        """Connections are loaded correctly."""
        maps_root = tmp_path
        _write_map(maps_root / "maps" / "map.txt")

        result, _ = load_map(maps_root, "maps/map.txt")
        assert result is not None
        graph, _, _ = result
        assert set(graph.connections) == {("base", "roof1"), ("roof1", "target")}

    def test_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns error."""
        maps_root = tmp_path
        result, error = load_map(maps_root, "maps/ghost.txt")
        assert result is None
        assert error is not None
        assert "ghost.txt" in error

    def test_directory_path_is_an_error(self, tmp_path: Path) -> None:
        """Passing a directory instead of file returns error."""
        maps_root = tmp_path
        (maps_root / "maps").mkdir()
        result, error = load_map(maps_root, "maps")
        assert result is None
        assert error is not None

    def test_malformed_first_line(self, tmp_path: Path) -> None:
        """Malformed map returns parse error with line number."""
        maps_root = tmp_path
        _write_map(maps_root / "maps" / "bad.txt", "not a map file\n")
        result, error = load_map(maps_root, "maps/bad.txt")
        assert result is None
        assert error is not None
        assert "line 1" in error

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty file returns parse error."""
        maps_root = tmp_path
        _write_map(maps_root / "maps" / "empty.txt", "")
        result, error = load_map(maps_root, "maps/empty.txt")
        assert result is None
        assert error is not None
        assert "line 1" in error

    def test_invalid_zone_name(self, tmp_path: Path) -> None:
        """Zone name with dash returns parse error."""
        maps_root = tmp_path
        _write_map(
            maps_root / "maps" / "dash.txt",
            "nb_drones: 1\n"
            "start_hub: bad-zone 0 0\n"
            "end_hub: end 10 10\n",
        )
        result, error = load_map(maps_root, "maps/dash.txt")
        assert result is None
        assert error is not None
        assert "line 2" in error

    def test_load_from_personal_dir(self, tmp_path: Path) -> None:
        """Can load maps from personal/ directory."""
        maps_root = tmp_path
        _write_map(maps_root / "personal" / "custom.txt")

        result, error = load_map(maps_root, "personal/custom.txt")
        assert error is None
        assert result is not None