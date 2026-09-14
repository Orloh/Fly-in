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

#: Subdirectories under maps_root to search for map files.
MAP_SUBDIRS = ("maps", "personal")


def list_maps(maps_root: str | Path) -> list[str]:
    """
    Return the sorted relative paths of every ``*.txt`` file under
    ``maps_root/maps/`` and ``maps_root/personal/``.

    Missing or empty directories yield an empty list; files in
    subdirectories are included with their relative path from
    ``maps_root`` (e.g. ``"maps/easy/01_linear_path.txt"``).
    """
    root = Path(maps_root)
    results: list[str] = []

    for subdir in MAP_SUBDIRS:
        subdir_path = root / subdir
        if not subdir_path.is_dir():
            continue

        for entry in subdir_path.rglob("*.txt"):
            if entry.is_file():
                # Get relative path from maps_root
                rel_path = entry.relative_to(root)
                results.append(str(rel_path))

    return sorted(results)


def load_map(
    maps_root: str | Path,
    rel_path: str | Path,
    canvas: tuple[int, int] = DEFAULT_CANVAS,
) -> tuple[LoadedMap | None, str | None]:
    """
    Load and lay out a map by relative path from maps_root.

    Parses the file, converts it to a graph + fleet, and maps world
    coordinates onto the canvas. Any parse or IO failure yields
    ``(None, message)`` instead of raising.
    """
    root = Path(maps_root)
    path = root / rel_path

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
