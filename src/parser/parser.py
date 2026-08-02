"""Text-file scanner that produces a ``ParsedMap`` from a raw map file.

This module handles line-oriented parsing: comment stripping, token
splitting, bracket-metadata extraction, and prefix-based classification.
No domain validation is performed — every value is stored as a string.
"""

from __future__ import annotations

# parse_map(path: str) -> ParsedMap
#
# 1. Open file, read all lines.
# 2. For each line:
#    a. Strip everything from '#' onward (comments).
#    b. Strip leading/trailing whitespace.
#    c. Skip if empty.
# 3. First non-empty line must be 'nb_drones: <int>'.
#    a. Split on ': ', validate format.
#    b. Convert to int, raise ParseError if not a positive integer.
#    c. Store as nb_drones.
# 4. Track `start_hub_found` and `end_hub_found` flags (both False).
# 5. For each remaining line:
#    a. Determine prefix by splitting on the first space:
#       - 'start_hub: name x y [metadata]'
#       - 'end_hub: name x y [metadata]'
#       - 'hub: name x y [metadata]'
#       - 'connection: nameA-nameB [metadata]'
#    b. Unrecognized prefix → raise ParseError.
# 6. For hub lines (start_hub, end_hub, hub):
#    a. Extract name, x (int), y (int) from the tokens after the prefix.
#    b. Extract bracket metadata with _parse_metadata(line).
#    c. Create ParsedZone(name, x, y, metadata).
#    d. start_hub: set flag, store as parsed.start_hub.
#    e. end_hub: set flag, store as parsed.end_hub.
#    f. hub: append to parsed.zones.
# 7. For connection lines:
#    a. Split the connection token by '-', validate exactly two parts.
#    b. Both parts must be non-empty zone names.
#    c. Extract bracket metadata with _parse_metadata(line).
#    d. Create ParsedConnection(zone_a, zone_b, metadata).
#    e. Append to parsed.connections.
# 8. After processing all lines:
#    a. If start_hub not found → raise ParseError.
#    b. If end_hub not found → raise ParseError.
# 9. Return ParsedMap(nb_drones, start_hub, end_hub, zones, connections).
#
# _parse_metadata(raw_line: str) -> dict[str, str]
#
# 1. Find the first '[' and the last ']' in the line.
# 2. If no brackets found → return empty dict.
# 3. If brackets are malformed (missing '[' or ']') → raise ParseError.
# 4. Extract the substring between the brackets.
# 5. Split by whitespace: each token is 'key=value'.
# 6. For each token:
#    a. Split by '=', ensure exactly two parts.
#    b. Store key → value in the dict.
# 7. Return the dict.
