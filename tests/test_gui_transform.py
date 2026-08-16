"""Tests for the GUI coordinate layout helper (Phase GUI-1)."""

from __future__ import annotations

from src.gui.transform import layout


class TestLayout:
    """Unit tests for the world-to-pixel coordinate mapping."""

    def test_horizontal_line_centered(self) -> None:
        points = {"A": (0, 0), "B": (100, 0)}
        result = layout(points, 200, 200, padding=20)
        assert result == {"A": (20, 100), "B": (180, 100)}

    def test_inverts_y_axis(self) -> None:
        points = {"bottom": (0, 0), "top": (10, 100)}
        result = layout(points, 200, 200, padding=20)
        assert result == {"top": (108, 20), "bottom": (92, 180)}

    def test_handles_negative_coordinates(self) -> None:
        points = {"a": (-10, -10), "b": (10, 10)}
        result = layout(points, 200, 200, padding=20)
        assert result == {"a": (20, 180), "b": (180, 20)}

    def test_single_point_is_centered(self) -> None:
        result = layout({"only": (5, 5)}, 200, 200, padding=20)
        assert result == {"only": (100, 100)}

    def test_preserves_aspect_ratio(self) -> None:
        points = {"min": (0, 0), "far_x": (200, 0), "far_y": (0, 100)}
        result = layout(points, 200, 200, padding=20)
        assert result["far_x"][0] - result["min"][0] == 160
        assert result["min"][1] - result["far_y"][1] == 80

    def test_empty_points(self) -> None:
        assert layout({}, 200, 200) == {}

    def test_pixels_inside_window(self) -> None:
        points = {"a": (0, 0), "b": (50, -30), "c": (-20, 40)}
        for _, (px, py) in layout(points, 800, 600, padding=40).items():
            assert isinstance(px, int)
            assert isinstance(py, int)
            assert 0 <= px <= 800
            assert 0 <= py <= 600
