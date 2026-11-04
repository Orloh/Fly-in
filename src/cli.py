"""Pure CLI output layer for the Fly-in simulation.

Formatters are side-effect-free and unit-testable; ``run`` wires
parsing, simulation and printing.
"""

from __future__ import annotations

import os
import sys
from typing import Iterator

from src.models import (
    Drone,
    DroneStatus,
    Graph,
    ParsedMap,
    ParsedZone,
    Schedule,
    TurnSnapshot,
    ZoneType,
)
from src.parser import build_graph, ParseError, parse_map
from src.palette import PALETTE, color_role
from src.simulation.engine import Simulation

ZONE_TYPE_ROLES: dict[ZoneType, str] = {
    ZoneType.NORMAL: "blue",
    ZoneType.PRIORITY: "green",
    ZoneType.RESTRICTED: "yellow",
    ZoneType.BLOCKED: "gray",
}


def paint(text: str, role: str, color: bool = False) -> str:
    """Wrap ``text`` in ANSI truecolor for ``role`` if ``color`` is True.

    No-op when ``color`` is False or role unknown.

    Args:
        text: The text to wrap.
        role: The Google palette role name to paint with.
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
    Google palette roles; uncolored zones keep the line's default role.

    Args:
        parsed: The parsed map to echo.
        color: Whether to enable ANSI color output.

    Returns:
        The map header lines, including a trailing blank separator.
    """
    lines: list[str] = []

    lines.append(paint(f"nb_drones: {parsed.nb_drones}", "blue", color))

    # Build name -> color_name lookup for all zones
    zone_colors: dict[str, str] = {}
    for z in [parsed.start_hub, parsed.end_hub, *parsed.zones]:
        zone_colors[z.name] = z.metadata.get("color", "none")

    lines.append(
        _format_zone_line(
            "start_hub: ", parsed.start_hub, "green", zone_colors, color
        )
    )
    lines.append(
        _format_zone_line(
            "end_hub: ", parsed.end_hub, "blue", zone_colors, color
        )
    )

    for z in parsed.zones:
        lines.append(
            _format_zone_line("hub: ", z, "white", zone_colors, color)
        )

    for c in parsed.connections:
        a_role = color_role(zone_colors.get(c.zone_a, "none")) or "gray"
        b_role = color_role(zone_colors.get(c.zone_b, "none")) or "gray"
        prefix = paint("connection: ", "gray", color)
        name_a = paint(c.zone_a, a_role, color)
        name_b = paint(c.zone_b, b_role, color)
        line = f"{prefix}{name_a}-{name_b}" + _format_metadata(c.metadata)
        lines.append(line)

    lines.append("")  # blank separator
    return lines


def format_turn(
    snapshot: TurnSnapshot,
    color: bool = False,
    zone_roles: dict[str, str] | None = None,
) -> str:
    """Format a snapshot's events as ``D{id}-{label}`` tokens.

    Args:
        snapshot: The logical end-of-turn snapshot.
        color: Whether to enable ANSI color output.
        zone_roles: Zone name to Google palette role mapping; unlisted
            zones default to ``blue``.

    Returns:
        The turn line, or an empty string when nothing to report.
    """
    if not snapshot.events:
        return ""
    parts: list[tuple[int, str]] = []
    for event in sorted(
        snapshot.events, key=lambda item: item.drone_id
    ):
        drone_part = paint(f"D{event.drone_id}", "yellow", color)
        if event.kind == "connection":
            label_part = _paint_connection(
                event.label, zone_roles, color
            )
        else:
            role = (zone_roles or {}).get(event.label, "blue")
            label_part = paint(event.label, role, color)
        parts.append((event.drone_id, f"{drone_part}-{label_part}"))
    return " ".join(token for _, token in sorted(parts))


def _paint_connection(
    connection: str,
    zone_roles: dict[str, str] | None,
    color: bool,
) -> str:
    """Paint a ``zone_a-zone_b`` connection name by endpoint roles."""
    zone_a, zone_b = connection.split("-", 1)
    roles = zone_roles or {}
    role_a = roles.get(zone_a, "blue")
    role_b = roles.get(zone_b, "blue")
    return f"{paint(zone_a, role_a, color)}-{paint(zone_b, role_b, color)}"


def format_makespan(makespan: int) -> str:
    """Format the final makespan summary line.

    Args:
        makespan: The makespan turn count.

    Returns:
        The ``makespan: N`` summary line.
    """
    return f"makespan: {makespan}"


def format_stats(schedule: Schedule) -> list[str]:
    """Format the stats block: leading separator, metrics, trailing blank.

    The trailing blank line separates consecutive map runs in
    ``make run-all``.

    Args:
        schedule: The schedule to summarize.

    Returns:
        The stats lines, or an empty list for an empty fleet.
    """
    metrics = format_metrics(schedule)
    if not metrics:
        return []
    return [
        "",
        "== Stats ==",
        *metrics,
        format_makespan(schedule.makespan),
        "",
    ]


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
        delivered = 0
        for action in drone_actions:
            if action.kind == "MOVE":
                moves += 1
                path_cost += action.turns_required
                delivered = action.turn + action.turns_required - 1
        arrivals.append(delivered)
    makespan = schedule.makespan
    moves_per_turn = (moves / makespan) if makespan else 0.0
    avg_turns = sum(arrivals) / n_drones
    return [
        f"moves_per_turn: {moves_per_turn:.2f}",
        f"avg_turns_per_drone: {avg_turns:.2f}",
        f"total_path_cost: {path_cost}",
    ]


def _has_future_action(sim: Simulation) -> bool:
    """Whether a waiting drone has a scheduled action still ahead.

    A pending action at or before the current turn means the engine tried
    to replay it but could not make progress (for example, a safety-net
    capacity block), so the caller should treat that as a deadlock.
    """
    for drone in sim.state.drones.values():
        if drone.status != DroneStatus.WAITING:
            continue
        if drone.schedule_index >= len(drone.schedule):
            continue
        action = drone.schedule[drone.schedule_index]
        if action.turn > sim.state.turn:
            return True
    return False


def simulate_turns(
    graph: Graph,
    drones: list[Drone],
    color: bool = False,
    show_stats: bool = False,
) -> Iterator[tuple[str, list[str]]]:
    """Step the simulation, yielding ``(line, conflicts)`` per turn.

    Args:
        graph: The routing graph.
        drones: The fleet to simulate.
        color: Whether to enable ANSI color output.
        show_stats: Whether to append the stats block after the turns.

    Yields:
        ``(formatted_line, conflicts)`` pairs for each simulation turn.
    """
    sim = Simulation(graph, drones)

    # Build zone_roles from graph: zone.name -> Google role (default blue)
    zone_roles: dict[str, str] = {}
    for name, zone in graph.zones.items():
        explicit = color_role(zone.color)
        zone_roles[name] = explicit or ZONE_TYPE_ROLES[zone.zone_type]

    while not sim.finished:
        result = sim.step()

        if sim.finished:
            # Final arrival turn: only emit if there were events
            if result.events:
                yield format_turn(
                    result, color, zone_roles
                ), result.conflicts
            break

        # Deadlock only when nothing moved, nothing is in transit, and no
        # drone has a future scheduled action left to replay.
        in_transit = any(
            d.status == DroneStatus.IN_TRANSIT
            for d in sim.state.drones.values()
        )
        line = format_turn(result, color, zone_roles)
        if (
            not result.events
            and not in_transit
            and not _has_future_action(sim)
        ):
            yield line, result.conflicts
            break

        yield line, result.conflicts

    if show_stats:
        for line in format_stats(sim.schedule):
            yield line, []


def _detect_color() -> bool:
    """Auto-detect whether stdout supports color."""
    return sys.stdout.isatty() and not os.getenv("NO_COLOR")


def build_output(
    map_path: str,
    debug: bool = False,
    color: bool | None = None,
    show_stats: bool = False,
    show_map: bool = False,
) -> tuple[list[str], list[str], int]:
    """Build the complete CLI output without side effects.

    Returns a tuple of (stdout_lines, stderr_lines, exit_code).
    exit_code is 0 for success, 1 for parse/IO errors.
    ``show_stats`` appends a stats block (``== Stats ==`` header, metrics,
    makespan); ``show_map`` echoes the normalized map header first.

    Args:
        map_path: Path to the map file.
        debug: Whether to collect engine conflicts for stderr.
        color: Force enable/disable ANSI color; None = auto-detect.
        show_stats: Whether to append the stats block.
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
    for line, conflicts in simulate_turns(
        graph,
        fleet,
        use_color,
        show_stats=show_stats,
    ):
        stdout_lines.append(line)
        if debug:
            stderr_lines.extend(conflicts)

    return stdout_lines, stderr_lines, 0


def run(
    map_path: str,
    debug: bool = False,
    color: bool | None = None,
    show_stats: bool = False,
    show_map: bool = False,
) -> None:
    """Parse map, run simulation, print turns.

    - ``debug``: print engine conflicts to stderr.
    - ``color``: force enable/disable ANSI color; None = auto-detect.
    - ``show_stats``: append the stats block (``== Stats ==`` header,
      metrics, makespan).
    - ``show_map``: echo the normalized map header before the turns.

    Args:
        map_path: Path to the map file.
        debug: Whether to print engine conflicts to stderr.
        color: Force enable/disable ANSI color; None = auto-detect.
        show_stats: Whether to append the stats block.
        show_map: Whether to echo the normalized map header first.
    """
    stdout_lines, stderr_lines, exit_code = build_output(
        map_path, debug, color, show_stats, show_map
    )
    for line in stdout_lines:
        print(line)
    for line in stderr_lines:
        print(line, file=sys.stderr)
    if exit_code != 0:
        sys.exit(exit_code)
