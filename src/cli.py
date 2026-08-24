"""Pure CLI output layer for the Fly-in simulation.

Mirrors the GUI's pure-helper + thin-run pattern: formatters are
side-effect-free and unit-testable; ``run`` wires parsing, simulation
and printing.
"""

from __future__ import annotations

import os
import sys
from typing import Iterator

from src.models import (
    Drone,
    Graph,
    ParsedMap,
    TurnResult,
)
from src.parser.converter import build_graph
from src.parser.errors import ParseError
from src.parser.parser import parse_map
from src.palette import PALETTE, color_role
from src.simulation.engine import Simulation


def paint(text: str, role: str, color: bool = False) -> str:
    """Wrap ``text`` in ANSI truecolor for ``role`` if ``color`` is True.

    No-op when ``color`` is False or role unknown.
    """
    if not color:
        return text
    rgb = PALETTE.get(role)
    if rgb is None:
        return text
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def _format_metadata(meta: dict[str, str]) -> str:
    """Render metadata dict as canonical '[k=v ...]' string (sorted keys)."""
    if not meta:
        return ""
    items = " ".join(f"{k}={v}" for k, v in sorted(meta.items()))
    return " [" + items + "]"


def format_map(parsed: ParsedMap, color: bool = False) -> list[str]:
    """Normalized map echo from ``ParsedMap``.

    Returns lines including a trailing blank separator line.
    Zone names are painted with their ``color=`` metadata mapped to
    rose-pine roles; uncolored zones keep the line's default role.
    """
    lines: list[str] = []

    lines.append(paint(f"nb_drones: {parsed.nb_drones}", "gold", color))

    # Build name -> color_name lookup for all zones
    zone_colors: dict[str, str] = {}
    for z in [parsed.start_hub, parsed.end_hub, *parsed.zones]:
        zone_colors[z.name] = z.metadata.get("color", "none")

    # start_hub: default role = text
    z = parsed.start_hub
    name_role = color_role(zone_colors.get(z.name, "none")) or "text"
    prefix = paint("start_hub: ", "text", color)
    name = paint(z.name, name_role, color)
    coords = paint(f"{z.x} {z.y}", "text", color)
    lines.append(f"{prefix}{name} {coords}" + _format_metadata(z.metadata))

    # end_hub: default role = text
    z = parsed.end_hub
    name_role = color_role(zone_colors.get(z.name, "none")) or "text"
    prefix = paint("end_hub: ", "text", color)
    name = paint(z.name, name_role, color)
    coords = paint(f"{z.x} {z.y}", "text", color)
    lines.append(f"{prefix}{name} {coords}" + _format_metadata(z.metadata))

    # regular hubs: default role = foam
    for z in parsed.zones:
        name_role = color_role(zone_colors.get(z.name, "none")) or "foam"
        prefix = paint("hub: ", "foam", color)
        name = paint(z.name, name_role, color)
        coords = paint(f"{z.x} {z.y}", "foam", color)
        lines.append(f"{prefix}{name} {coords}" + _format_metadata(z.metadata))

    # connections: default role = pine, each endpoint independent
    for c in parsed.connections:
        a_role = color_role(zone_colors.get(c.zone_a, "none")) or "pine"
        b_role = color_role(zone_colors.get(c.zone_b, "none")) or "pine"
        prefix = paint("connection: ", "pine", color)
        name_a = paint(c.zone_a, a_role, color)
        name_b = paint(c.zone_b, b_role, color)
        line = f"{prefix}{name_a}-{name_b}" + _format_metadata(c.metadata)
        lines.append(line)

    lines.append("")  # blank separator
    return lines


def format_turn(
    result: TurnResult,
    color: bool = False,
    zone_roles: dict[str, str] | None = None,
) -> str:
    """Format a single turn's movements as ``D{id}-{to_zone} ...``.

    Returns empty string when no movements.
    ``zone_roles`` maps zone names to rose-pine roles; default for
    unlisted zones is ``foam``.
    """
    if not result.movements:
        return ""
    parts = []
    for mv in sorted(result.movements, key=lambda m: m.drone_id):
        drone_part = paint(f"D{mv.drone_id}", "gold", color)
        role = (zone_roles or {}).get(mv.to_zone, "foam")
        zone_part = paint(mv.to_zone, role, color)
        parts.append(f"{drone_part}-{zone_part}")
    return " ".join(parts)


def simulate(
    graph: Graph, drones: list[Drone], color: bool = False
) -> Iterator[str]:
    """Step the simulation, yielding one line per turn.

    - Yields ``format_turn`` result for every turn (empty string for
      in-transit-only turns).
    - Stops on ``finished`` (final arrival turn without movements is not
      yielded).
    - Deadlock guard: breaks when a turn has no movements AND no drone
      is ``IN_TRANSIT``.
    """
    sim = Simulation(graph, drones)

    # Build zone_roles from graph: zone.name -> rose-pine role (default foam)
    zone_roles: dict[str, str] = {}
    for name, zone in graph.zones.items():
        zone_roles[name] = color_role(zone.color) or "foam"

    while not sim.finished:
        result = sim.step()

        if sim.finished:
            # Final arrival turn: only emit if there were movements
            if result.movements:
                yield format_turn(result, color, zone_roles)
            break

        # Deadlock: nothing moved and nothing in flight -> nothing will ever
        # change
        in_transit = any(
            d.status.value == "in_transit" for d in sim.state.drones.values()
        )
        if not result.movements and not in_transit:
            break

        yield format_turn(result, color, zone_roles)


def _detect_color() -> bool:
    """Auto-detect whether stdout supports color."""
    return sys.stdout.isatty() and not os.getenv("NO_COLOR")


def run(map_path: str, debug: bool = False, color: bool | None = None) -> None:
    """Parse map, run simulation, print turns.

    - ``debug``: print engine conflicts to stderr.
    - ``color``: force enable/disable ANSI color; None = auto-detect.
    """
    use_color = _detect_color() if color is None else color

    try:
        parsed = parse_map(map_path)
    except ParseError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
    except OSError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    graph, fleet = build_graph(parsed)

    # Print map header
    for line in format_map(parsed, use_color):
        print(line)

    # Print simulation turns
    for line in simulate(graph, fleet, use_color):
        print(line)

    # Debug: re-run to print conflicts to stderr
    if debug:
        sim = Simulation(graph, fleet)
        while not sim.finished:
            result = sim.step()
            for conflict in result.conflicts:
                print(conflict, file=sys.stderr)
            if sim.finished:
                break
