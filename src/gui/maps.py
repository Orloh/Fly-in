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
    """Return the sorted relative paths of every ``*.txt`` map file.

    Searches ``maps_root/maps/`` and ``maps_root/personal/``. Missing or
    empty directories yield an empty list; files in subdirectories are
    included with their relative path from ``maps_root`` (e.g.
    ``"maps/easy/01_linear_path.txt"``).

    Args:
        maps_root: Root directory containing ``maps/`` and ``personal/``.

    Returns:
        The sorted relative paths of all found map files.
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


def list_map_folders(maps_root: str | Path) -> list[str]:
    """Return the sorted top-level folders that hold map files.

    Each immediate subdirectory of ``maps/`` containing at least one
    ``*.txt`` file becomes a folder (e.g. ``"maps/easy"``); ``personal/``
    itself is a folder when it holds maps. Folder paths are relative to
    ``maps_root``.

    Args:
        maps_root: Root directory containing ``maps/`` and ``personal/``.

    Returns:
        The sorted relative folder paths with at least one map file.
    """
    root = Path(maps_root)
    folders: set[str] = set()

    for subdir in MAP_SUBDIRS:
        subdir_path = root / subdir
        if not subdir_path.is_dir():
            continue
        if subdir == "personal":
            if any(subdir_path.glob("*.txt")):
                folders.add("personal")
            continue
        for entry in subdir_path.iterdir():
            if entry.is_dir() and any(entry.rglob("*.txt")):
                folders.add(f"{subdir}/{entry.name}")

    return sorted(folders)


def list_maps_in_folder(maps_root: str | Path, folder: str) -> list[str]:
    """Return the sorted map paths inside a folder.

    ``folder`` is a relative path from ``maps_root`` (e.g. ``"maps/easy"``
    or ``"personal"``). Unknown or empty folders yield an empty list.

    Args:
        maps_root: Root directory containing ``maps/`` and ``personal/``.
        folder: The folder's relative path from ``maps_root``.

    Returns:
        The sorted map paths within the folder, or [] when absent.
    """
    folder_path = Path(maps_root) / folder
    if not folder_path.is_dir():
        return []
    return sorted(
        str(entry.relative_to(Path(maps_root)))
        for entry in folder_path.rglob("*.txt")
        if entry.is_file()
    )


def resolve_maps_root(map_path: str | Path) -> Path:
    """Locate the directory directly containing the ``maps/`` catalogue.

    Walks up from ``map_path`` to the nearest parent that holds a
    ``maps/`` directory (this also covers layouts where ``personal/``
    lives inside ``maps/``); falls back to ``Path("maps")`` otherwise.

    Args:
        map_path: Path to a map file, absolute or relative.

    Returns:
        The maps root whose ``maps/`` subdirectory contains the file.
    """
    path = Path(map_path).resolve()
    for parent in path.parents:
        if (parent / "maps").is_dir():
            return parent
    return Path("maps").resolve()


def load_map(
    maps_root: str | Path,
    rel_path: str | Path,
    canvas: tuple[int, int] = DEFAULT_CANVAS,
) -> tuple[LoadedMap | None, str | None]:
    """Load and lay out a map by relative path from maps_root.

    Parses the file, converts it to a graph + fleet, and maps world
    coordinates onto the canvas. Any parse or IO failure yields
    ``(None, message)`` instead of raising.

    Args:
        maps_root: Root directory containing ``maps/`` and ``personal/``.
        rel_path: The map file's relative path from ``maps_root``.
        canvas: The virtual canvas size to lay the map onto.

    Returns:
        A ``(loaded_map, error_message)`` tuple; on failure the loaded
        map is None and the message describes the problem.
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
