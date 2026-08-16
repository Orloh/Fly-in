"""
Pure coordinate transforms for the GUI layer.

Converts zone world coordinates into window pixel positions. Contains
no pygame logic: it only produces the positions that the drawing layer
(app) turns into visible pixels, keeping the math unit-testable.
"""

from __future__ import annotations

from collections.abc import Mapping


def layout(
    points: Mapping[str, tuple[float, float]],
    width: int,
    height: int,
    padding: int = 40,
) -> dict[str, tuple[int, int]]:
    """
    Map zone coordinates onto pixel positions fitted to the window.

    Uses a uniform scale so the map's aspect ratio is preserved. World
    +y maps upward on screen. Empty, single-point, and degenerate
    inputs are handled gracefully.
    """
    if not points:
        return {}

    xs = [x for x, _ in points.values()]
    ys = [y for _, y in points.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    usable_w = max(width - 2 * padding, 1)
    usable_h = max(height - 2 * padding, 1)

    span_x = max_x - min_x
    span_y = max_y - min_y

    if span_x <= 0 and span_y <= 0:
        return {name: (width // 2, height // 2) for name in points}

    scales = [
        usable_w / span_x if span_x > 0 else None,
        usable_h / span_y if span_y > 0 else None,
    ]
    scale = min(s for s in scales if s is not None)

    rendered_w = span_x * scale if span_x > 0 else 0.0
    rendered_h = span_y * scale if span_y > 0 else 0.0

    offset_x = padding + (usable_w - rendered_w) / 2
    offset_y = padding + (usable_h - rendered_h) / 2

    result: dict[str, tuple[int, int]] = {}
    for name, (x, y) in points.items():
        px = offset_x + (x - min_x) * scale if span_x > 0 else offset_x
        py = offset_y + (max_y - y) * scale if span_y > 0 else offset_y
        result[name] = (round(px), round(py))

    return result
