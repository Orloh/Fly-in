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
from src.simulation.engine import Simulation


#: Rose-pine truecolor palette (r, g, b).
PALETTE: dict[str, tuple[int, int, int]] = {
    "gold": (246, 193, 119),
    "foam": (156, 207, 216),
    "rose": (235, 111, 146),
    "pine": (49, 116, 143),
    "text": (224, 222, 244),
    "muted": (110, 106, 134),
}


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
    return f" [{items}]"


def format_map(parsed: ParsedMap, color: bool = False) -> list[str]:
    """Normalized map echo from ``ParsedMap``.

    Returns lines including a trailing blank separator line.
    """
    lines: list[str] = []

    lines.append(paint(f"nb_drones: {parsed.nb_drones}", "gold", color))
    start_hub = parsed.start_hub
    lines.append(
        paint(
            f"start_hub: {start_hub.name} {start_hub.x} {start_hub.y}",
            "text",
            color,
        )
        + _format_metadata(start_hub.metadata)
    )
    end_hub = parsed.end_hub
    lines.append(
        paint(
            f"end_hub: {end_hub.name} {end_hub.x} {end_hub.y}",
            "text",
            color,
        )
        + _format_metadata(end_hub.metadata)
    )

    for z in parsed.zones:
        lines.append(
            paint(f"hub: {z.name} {z.x} {z.y}", "foam", color)
            + _format_metadata(z.metadata)
        )

    for c in parsed.connections:
        lines.append(
            paint(f"connection: {c.zone_a}-{c.zone_b}", "pine", color)
            + _format_metadata(c.metadata)
        )

    lines.append("")  # blank separator
    return lines


def format_turn(result: TurnResult, color: bool = False) -> str:
    """Format a single turn's movements as ``D{id}-{to_zone} ...``.

    Returns empty string when no movements.
    """
    if not result.movements:
        return ""
    parts = []
    for mv in sorted(result.movements, key=lambda m: m.drone_id):
        drone_part = paint(f"D{mv.drone_id}", "gold", color)
        zone_part = paint(mv.to_zone, "foam", color)
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

    while not sim.finished:
        result = sim.step()

        if sim.finished:
            # Final arrival turn: only emit if there were movements
            if result.movements:
                yield format_turn(result, color)
            break

        # Deadlock: nothing moved and nothing in flight -> nothing will ever
        # change
        in_transit = any(
            d.status.value == "in_transit" for d in sim.state.drones.values()
        )
        if not result.movements and not in_transit:
            break

        yield format_turn(result, color)


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
