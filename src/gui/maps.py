"""Pure map-file helpers for the GUI layer.

Discovery of the ``maps/`` catalogue (``list_maps``) and the load +
convert + layout pipeline behind the map picker (``load_map``).
Contains no pygame logic so it stays unit-testable.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

from src.gui.transform import layout
from src.models import Drone, Graph
from src.parser import build_graph, ParseError, parse_map

#: Shape of a successfully loaded map: graph, fleet, and pixel positions.
LoadedMap: TypeAlias = tuple[
    Graph, list[Drone], dict[str, tuple[int, int]]
]

#: Default low-res canvas the map is laid out onto (see GUI_PLAN.md).
DEFAULT_CANVAS = (640, 360)


def list_maps(maps_dir: str | Path) -> list[str]:
    """
    Return the sorted names of every ``*.map`` file in the directory.

    Missing or empty directories yield an empty list; only top-level
    files count, never subdirectories.
    """
    path = Path(maps_dir)

    if not path.is_dir():
        return []

    maps = [
        entry.name
        for entry in path.iterdir()
        if entry.is_file() and entry.name.endswith('.map')
    ]

    return sorted(maps)


def load_map(
    map_path: str | Path,
    canvas: tuple[int, int] = DEFAULT_CANVAS,
) -> tuple[LoadedMap | None, str | None]:
    """
    Load and lay out a map, returning state or a short error message.

    Parses the file, converts it to a graph + fleet, and maps world
    coordinates onto the canvas. Any parse or IO failure yields
    ``(None, message)`` instead of raising.
    """
    path = Path(map_path)

    try:
        parsed = parse_map(str(path))
        graph, fleet = build_graph(parsed)
        points = {
            name: (float(zone.x), float(zone.y))
            for name, zone in graph.zones.items()
        }
        positions = layout(points, *canvas)
        return (graph, fleet, positions), None
    except OSError as error:
        return None, f"Could not read map file '{path.name}': {error}"
    except ParseError as error:
        return None, f"Map file '{path.name}' is invalid: {error}"
