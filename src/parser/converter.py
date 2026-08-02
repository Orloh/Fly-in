"""Parser-to-domain translator that builds a ``Graph`` and drone fleet.

Takes a ``ParsedMap`` and performs all domain-level validation: zone
types, capacities, duplicate connections, and zone-name constraints.
Returns fully-validated ``Graph`` and ``Drone`` objects.
"""

from __future__ import annotations

# build_graph(parsed: ParsedMap) -> tuple[Graph, list[Drone]]
#
# 1. Convert all zones (start_hub, end_hub, zones list) into Zone objects.
#    a. _convert_zone(parsed_zone, is_start=False, is_end=False) → Zone.
# 2. Build a dict[str, Zone] from the converted zones.
# 3. Validate all connections and build Connection objects.
#    a. _convert_connection(parsed_conn, zone_names) → Connection.
#    b. Check for duplicate connections via canonical key.
# 4. Build Graph(zones, connections).
# 5. Create nb_drones × Drone objects:
#    a. Each starts at start_hub, targets end_hub.
#    b. Status = WAITING, path = empty, current_zone = start_hub name.
# 6. Return (graph, drone_list).
#
# _convert_zone(
#     parsed: ParsedZone, is_start: bool, is_end: bool
# ) → Zone
#
# 1. Extract 'zone' from metadata, default 'normal'.
#    a. Validate against allowed values:
#       'normal' → ZoneType.NORMAL
#       'priority' → ZoneType.PRIORITY
#       'restricted' → ZoneType.RESTRICTED
#       'blocked' → ZoneType.BLOCKED
#    b. Unknown value → raise ParseError.
# 2. Extract 'max_drones' from metadata, default '1'.
#    a. Convert to int, must be >= 1 → raise ParseError otherwise.
# 3. Extract 'color' from metadata, default 'none'.
# 4. Create Zone(
#       name=parsed.name,
#       x=parsed.x, y=parsed.y,
#       zone_type=ZoneType,
#       max_drones=max_drones_int,
#       color=color_str,
#       is_start_hub=is_start,
#       is_end_hub=is_end,
#    ).
#    a. The Zone model's field_validator will reject names with '-' or ' '.
#    b. Pydantic's Field(ge=1) will catch negative max_drones.
# 5. Return the Zone.
#
# _convert_connection(
#     parsed: ParsedConnection, known_zones: set[str]
# ) -> Connection
#
# 1. Both zone_a and zone_b must exist in known_zones → raise ParseError.
# 2. Extract 'max_link_capacity' from metadata, default '1'.
#    a. Convert to int, must be >= 1 → raise ParseError otherwise.
# 3. Create Connection(zone_a, zone_b, max_link_capacity).
#    a. Pydantic's Field(ge=1) validates the capacity.
# 4. Return the Connection.
