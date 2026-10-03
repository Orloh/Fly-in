"""Pure CLI output layer for the Fly-in simulation.

Mirrors the GUI's pure-helper + thin-run pattern: formatters are
side-effect-free and unit-testable; ``run`` wires parsing, simulation
and printing.
"""

from __future__ import annotations

import os
import sys
from typing import Iterator, TypeAlias

from src.models import (
    Drone,
    DroneStatus,
    Graph,
    ParsedMap,
    ParsedZone,
    Schedule,
    TurnResult,
)
from src.parser import build_graph, ParseError, parse_map
from src.palette import PALETTE, color_role
from src.simulation.engine import Simulation

# Type aliases for clarity
RGB: TypeAlias = tuple[int, int, int]
Positions: TypeAlias = dict[str, tuple[int, int]]
ZoneRoles: TypeAlias = dict[str, str]


def paint(text: str, role: str, color: bool = False) -> str:
    """Wrap ``text`` in ANSI truecolor for ``role`` if ``color`` is True.

    No-op when ``color`` is False or role unknown.

    Args:
        text: The text to wrap.
        role: The rose-pine role name to paint with.
        color: Whether to enable ANSI color output.

    Returns:
        ``text`` wrapped in ANSI truecolor, or ``text`` unchanged.
    """
    if not color:
        return text
    rgb = PALETTE.get(role)
    if rgb is None:
        return text
    r, g, b = rgb
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def _format_zone_line(
    prefix: str,
    zone: ParsedZone,
    default_role: str,
    zone_colors: dict[str, str],
    color: bool,
) -> str:
    """Format a single zone line: prefix + painted name + coords + metadata."""
    name_role = color_role(zone_colors.get(zone.name, "none")) or default_role
    prefix_p = paint(prefix, default_role, color)
    name = paint(zone.name, name_role, color)
    coords = paint(f"{zone.x} {zone.y}", default_role, color)
    return f"{prefix_p}{name} {coords}" + _format_metadata(zone.metadata)


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

    Args:
        parsed: The parsed map to echo.
        color: Whether to enable ANSI color output.

    Returns:
        The map header lines, including a trailing blank separator.
    """
    lines: list[str] = []

    lines.append(paint(f"nb_drones: {parsed.nb_drones}", "gold", color))

    # Build name -> color_name lookup for all zones
    zone_colors: dict[str, str] = {}
    for z in [parsed.start_hub, parsed.end_hub, *parsed.zones]:
        zone_colors[z.name] = z.metadata.get("color", "none")

    lines.append(
        _format_zone_line(
            "start_hub: ", parsed.start_hub, "text", zone_colors, color
        )
    )
    lines.append(
        _format_zone_line(
            "end_hub: ", parsed.end_hub, "text", zone_colors, color
        )
    )

    for z in parsed.zones:
        lines.append(_format_zone_line("hub: ", z, "foam", zone_colors, color))

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
    in_flight: dict[int, str] | None = None,
) -> str:
    """Format a turn's movements as ``D{id}-{to_zone} ...``.

    Appends ``D{id}-{from}-{to}`` for drones still in flight toward a
    restricted zone. Returns empty string when nothing to report.
    ``zone_roles`` maps zone names to rose-pine roles; default for
    unlisted zones is ``foam``.

    Args:
        result: The turn's movements and conflicts.
        color: Whether to enable ANSI color output.
        zone_roles: Zone name to rose-pine role mapping; unlisted
            zones default to ``foam``.
        in_flight: In-flight drone id to connection name pairs.

    Returns:
        The turn line, or an empty string when nothing to report.
    """
    if not result.movements and not in_flight:
        return ""
    parts: list[tuple[int, str]] = []
    for mv in sorted(result.movements, key=lambda m: m.drone_id):
        drone_part = paint(f"D{mv.drone_id}", "gold", color)
        role = (zone_roles or {}).get(mv.to_zone, "foam")
        zone_part = paint(mv.to_zone, role, color)
        parts.append((mv.drone_id, f"{drone_part}-{zone_part}"))
    for drone_id, connection in (in_flight or {}).items():
        drone_part = paint(f"D{drone_id}", "gold", color)
        connection_part = _paint_connection(connection, zone_roles, color)
        parts.append((drone_id, f"{drone_part}-{connection_part}"))
    return " ".join(token for _, token in sorted(parts))


def _paint_connection(
    connection: str,
    zone_roles: dict[str, str] | None,
    color: bool,
) -> str:
    """Paint a ``zone_a-zone_b`` connection name by endpoint roles."""
    zone_a, zone_b = connection.split("-", 1)
    roles = zone_roles or {}
    role_a = roles.get(zone_a, "foam")
    role_b = roles.get(zone_b, "foam")
    return f"{paint(zone_a, role_a, color)}-{paint(zone_b, role_b, color)}"


def format_makespan(makespan: int) -> str:
    """Format the final makespan summary line.

    Args:
        makespan: The makespan turn count.

    Returns:
        The ``makespan: N`` summary line.
    """
    return f"makespan: {makespan}"


def format_metrics(schedule: Schedule) -> list[str]:
    """Format secondary scoring metrics (subject VII.6).

    Returns the average moves per turn, the average turns per drone, and
    the total weighted path cost across all drones. Empty for an empty
    fleet.

    Args:
        schedule: The schedule to summarize.

    Returns:
        The metrics lines, or an empty list for an empty fleet.
    """
    actions = schedule.actions
    if not actions:
        return []
    n_drones = len(actions)
    moves = 0
    path_cost = 0
    arrivals: list[int] = []
    for drone_actions in actions.values():
        arrival = 0
        for action in drone_actions:
            if action.kind == "MOVE":
                moves += 1
                path_cost += action.turns_required
                arrival = action.turn + action.turns_required
            else:
                arrival = max(arrival, action.turn)
        arrivals.append(arrival)
    makespan = schedule.makespan
    moves_per_turn = (moves / makespan) if makespan else 0.0
    avg_turns = sum(arrivals) / n_drones
    return [
        f"moves_per_turn: {moves_per_turn:.2f}",
        f"avg_turns_per_drone: {avg_turns:.2f}",
        f"total_path_cost: {path_cost}",
    ]


def simulate(
    graph: Graph, drones: list[Drone], color: bool = False
) -> Iterator[str]:
    """Step the simulation, yielding one line per turn.

    - Yields ``format_turn`` result for every turn (empty string only
      for a fully idle turn).
    - Stops on ``finished`` (final arrival turn without movements is not
      yielded).
    - Deadlock guard: breaks when a turn has no movements AND no drone
      is ``IN_TRANSIT``.

    Args:
        graph: The routing graph.
        drones: The fleet to simulate.
        color: Whether to enable ANSI color output.

    Yields:
        One formatted line per simulation turn.
    """
    for line, _ in _simulate_raw(graph, drones, color):
        yield line


def _in_flight_after(
    sim: Simulation,
    in_flight_before: dict[int, tuple[str, str]],
) -> dict[int, str]:
    """Connection per drone still transiting after ``sim.step()``.

    A drone continues an in-flight hop only when its
    ``(current_zone, transit_destination)`` is unchanged across the
    turn; arrivals (and hops launched on arrival) are excluded because
    they are already reported as movements.
    """
    in_flight: dict[int, str] = {}
    for d in sim.state.drones.values():
        if d.id not in in_flight_before:
            continue
        if d.status != DroneStatus.IN_TRANSIT:
            continue
        if d.current_zone is None or d.transit_destination is None:
            continue
        if in_flight_before[d.id] != (
            d.current_zone,
            d.transit_destination,
        ):
            continue
        in_flight[d.id] = f"{d.current_zone}-{d.transit_destination}"
    return in_flight


def _simulate_raw(
    graph: Graph,
    drones: list[Drone],
    color: bool = False,
    show_makespan: bool = False,
    show_metrics: bool = False,
) -> Iterator[tuple[str, list[str]]]:
    """Internal: step simulation, yielding (line, conflicts) per turn."""
    sim = Simulation(graph, drones)

    # Build zone_roles from graph: zone.name -> rose-pine role (default foam)
    zone_roles: dict[str, str] = {}
    for name, zone in graph.zones.items():
        zone_roles[name] = color_role(zone.color) or "foam"

    while not sim.finished:
        in_flight_before = {
            d.id: (d.current_zone, d.transit_destination)
            for d in sim.state.drones.values()
            if d.status == DroneStatus.IN_TRANSIT
            and d.current_zone is not None
            and d.transit_destination is not None
        }
        result = sim.step()
        in_flight = _in_flight_after(sim, in_flight_before)

        if sim.finished:
            # Final arrival turn: only emit if there were movements
            if result.movements:
                yield format_turn(
                    result, color, zone_roles, in_flight
                ), result.conflicts
            break

        # Deadlock: nothing moved and nothing in flight -> nothing will ever
        # change
        in_transit = any(
            d.status == DroneStatus.IN_TRANSIT
            for d in sim.state.drones.values()
        )
        if not result.movements and not in_transit:
            break

        yield format_turn(result, color, zone_roles, in_flight), (
            result.conflicts
        )

    if show_metrics:
        for line in format_metrics(sim.schedule):
            yield line, []
    if show_makespan:
        yield format_makespan(sim.schedule.makespan), []


def _detect_color() -> bool:
    """Auto-detect whether stdout supports color."""
    return sys.stdout.isatty() and not os.getenv("NO_COLOR")


def build_output(
    map_path: str,
    debug: bool = False,
    color: bool | None = None,
    show_makespan: bool = False,
    show_metrics: bool = False,
    show_map: bool = False,
) -> tuple[list[str], list[str], int]:
    """Build the complete CLI output without side effects.

    Returns a tuple of (stdout_lines, stderr_lines, exit_code).
    exit_code is 0 for success, 1 for parse/IO errors.
    ``show_makespan`` appends a final ``makespan: N`` line;
    ``show_metrics`` appends secondary scoring metrics; ``show_map``
    echoes the normalized map header before the turns.

    Args:
        map_path: Path to the map file.
        debug: Whether to collect engine conflicts for stderr.
        color: Force enable/disable ANSI color; None = auto-detect.
        show_makespan: Whether to append a final ``makespan: N`` line.
        show_metrics: Whether to append secondary scoring metrics.
        show_map: Whether to echo the normalized map header first.

    Returns:
        A ``(stdout_lines, stderr_lines, exit_code)`` tuple.
    """
    use_color = _detect_color() if color is None else color
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    try:
        parsed = parse_map(map_path)
        graph, fleet = build_graph(parsed)
    except ParseError as err:
        stderr_lines.append(f"Error: {err}")
        return stdout_lines, stderr_lines, 1
    except OSError as err:
        stderr_lines.append(f"Error: {err}")
        return stdout_lines, stderr_lines, 1

    # Map header (opt-in; subject VII.5 stdout is movement lines only)
    if show_map:
        stdout_lines.extend(format_map(parsed, use_color))

    # Simulation turns
    for line, conflicts in _simulate_raw(
        graph,
        fleet,
        use_color,
        show_makespan=show_makespan,
        show_metrics=show_metrics,
    ):
        stdout_lines.append(line)
        if debug:
            stderr_lines.extend(conflicts)

    return stdout_lines, stderr_lines, 0


def run(
    map_path: str,
    debug: bool = False,
    color: bool | None = None,
    show_makespan: bool = False,
    show_metrics: bool = False,
    show_map: bool = False,
) -> None:
    """Parse map, run simulation, print turns.

    - ``debug``: print engine conflicts to stderr.
    - ``color``: force enable/disable ANSI color; None = auto-detect.
    - ``show_makespan``: print a final ``makespan: N`` line.
    - ``show_metrics``: print secondary scoring metrics.
    - ``show_map``: echo the normalized map header before the turns.

    Args:
        map_path: Path to the map file.
        debug: Whether to print engine conflicts to stderr.
        color: Force enable/disable ANSI color; None = auto-detect.
        show_makespan: Whether to print a final ``makespan: N`` line.
        show_metrics: Whether to print secondary scoring metrics.
        show_map: Whether to echo the normalized map header first.
    """
    stdout_lines, stderr_lines, exit_code = build_output(
        map_path, debug, color, show_makespan, show_metrics, show_map
    )
    for line in stdout_lines:
        print(line)
    for line in stderr_lines:
        print(line, file=sys.stderr)
    if exit_code != 0:
        sys.exit(exit_code)
