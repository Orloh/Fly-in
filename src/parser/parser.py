"""Text-file scanner that produces a ``ParsedMap`` from a raw map file.

This module handles line-oriented parsing: comment stripping, token
splitting, bracket-metadata extraction, and prefix-based classification.
No domain validation is performed — every value is stored as a string.
"""

from __future__ import annotations
from src.models import ParsedMap
from src.parser.errors import ParseError

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
#    b. Extract bracket metadata with _parse_metadata(line, line_number).
#    c. Create ParsedZone(name, x, y, metadata).
#    d. start_hub: set flag, store as parsed.start_hub.
#    e. end_hub: set flag, store as parsed.end_hub.
#    f. hub: append to parsed.zones.
# 7. For connection lines:
#    a. Split the connection token by '-', validate exactly two parts.
#    b. Both parts must be non-empty zone names.
#    c. Extract bracket metadata with _parse_metadata(line, line_number).
#    d. Create ParsedConnection(zone_a, zone_b, metadata).
#    e. Append to parsed.connections.
# 8. After processing all lines:
#    a. If start_hub not found → raise ParseError.
#    b. If end_hub not found → raise ParseError.
# 9. Return ParsedMap(nb_drones, start_hub, end_hub, zones, connections).


def parse_map(path: str) -> ParsedMap:
    """Parse a map file into a ParsedMap.

    Placeholder — the real implementation lands in a later step.
    """
    raise NotImplementedError


def _parse_metadata(raw_line: str, line_number: int) -> dict[str, str]:
    """Extract the "[key=value ...]" metadata of a map line.

    Returns an empty dict when no brackets are present. Raises
    ParseError on malformed brackets or key/value tokens.
    """
    open_index = raw_line.find("[")
    close_index = raw_line.rfind("]")

    if open_index == -1 and close_index == -1:
        return {}
    elif open_index == -1 or close_index == -1:
        raise ParseError(line_number, "metadata missing '[' or ']'")
    elif open_index > close_index:
        raise ParseError(line_number, "metadata brackets out of order")

    metadata_text = raw_line[open_index + 1:close_index]
    metadata_list = metadata_text.split()
    if not metadata_list:
        return {}

    result: dict[str, str] = {}
    for token in metadata_list:
        parts = token.split("=")
        if len(parts) != 2:
            raise ParseError(
                line_number, f"malformed metadata token '{token}'"
            )
        key, value = parts
        if not key:
            raise ParseError(line_number, "metadata key cannot be empty")
        if not value:
            raise ParseError(
                line_number, f"metadata value for '{key}' cannot be empty"
            )
        result[key] = value
    return result
