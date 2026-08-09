"""Parser-to-domain translator that builds a ``Graph`` and drone fleet.

Takes a ``ParsedMap`` and performs all domain-level validation: zone
types, capacities, duplicate connections, and zone-name constraints.
Returns fully-validated ``Graph`` and ``Drone`` objects.
"""

from __future__ import annotations

from src.models import (
    Connection,
    Drone,
    Graph,
    ParsedConnection,
    ParsedMap,
    ParsedZone,
    Zone,
    ZoneType,
)
from src.parser.errors import ParseError


def build_graph(parsed: ParsedMap) -> tuple[Graph, list[Drone]]:
    """Convert a parsed map into a Graph and a fleet of drones."""
    start_zone = _convert_zone(parsed.start_hub, is_start=True, is_end=False)
    end_zone = _convert_zone(parsed.end_hub, is_start=False, is_end=True)

    if start_zone.name == end_zone.name:
        raise ParseError(
            parsed.end_hub.line_number,
            "start_hub and end_hub cannot share a name",
        )

    zones: dict[str, Zone] = {
        start_zone.name: start_zone,
        end_zone.name: end_zone,
    }

    for z in parsed.zones:
        zone = _convert_zone(z, is_start=False, is_end=False)
        if zone.name in zones:
            raise ParseError(
                z.line_number, f"duplicate zone name '{zone.name}'"
            )
        zones[zone.name] = zone

    connections: dict[tuple[str, str], Connection] = {}
    known = set(zones)

    for c in parsed.connections:
        connection = _convert_connection(c, known)
        if connection.key in connections:
            raise ParseError(
                c.line_number,
                f"duplicate connection '{c.zone_a}-{c.zone_b}'",
            )
        connections[connection.key] = connection

    graph = Graph(zones=zones, connections=connections)

    drones = [
        Drone(
            id=i,
            current_zone=start_zone.name,
            target_zone=end_zone.name,
        )
        for i in range(1, parsed.nb_drones + 1)
    ]

    return graph, drones


def _convert_zone(
    parsed: ParsedZone, is_start: bool, is_end: bool
) -> Zone:
    """Convert one ParsedZone into a validated Zone."""
    if "-" in parsed.name or " " in parsed.name:
        raise ParseError(
            parsed.line_number,
            "zone names cannot contain dashes or spaces",
        )

    token = parsed.metadata.get("zone", "normal")
    try:
        zone_type = ZoneType(token)
    except ValueError:
        raise ParseError(
            parsed.line_number, "unknown zone type"
        ) from None

    token = parsed.metadata.get("max_drones", "1")
    try:
        max_drones = int(token)
    except ValueError:
        raise ParseError(
            parsed.line_number, "max_drones must be an integer"
        ) from None
    if max_drones < 1:
        raise ParseError(
            parsed.line_number, "max_drones must be a positive integer"
        )

    color = parsed.metadata.get("color", "none")

    return Zone(
        name=parsed.name,
        x=parsed.x,
        y=parsed.y,
        zone_type=zone_type,
        color=color,
        max_drones=max_drones,
        is_start_hub=is_start,
        is_end_hub=is_end,
    )


def _convert_connection(
    parsed: ParsedConnection, known_zones: set[str]
) -> Connection:
    """Convert one ParsedConnection into a validated Connection."""
    if parsed.zone_a not in known_zones:
        raise ParseError(
            parsed.line_number, f"unknown zone '{parsed.zone_a}'"
        )
    if parsed.zone_b not in known_zones:
        raise ParseError(
            parsed.line_number, f"unknown zone '{parsed.zone_b}'"
        )

    token = parsed.metadata.get("max_link_capacity", "1")

    try:
        capacity = int(token)
    except ValueError:
        raise ParseError(
            parsed.line_number, "max_link_capacity must be an integer"
        ) from None
    if capacity < 1:
        raise ParseError(
            parsed.line_number,
            "max_link_capacity must be a positive integer",
        )

    return Connection(
        zone_a=parsed.zone_a,
        zone_b=parsed.zone_b,
        max_link_capacity=capacity,
    )
