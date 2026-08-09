"""Text-file scanner that produces a ``ParsedMap`` from a raw map file.

This module handles line-oriented parsing: comment stripping, token
splitting, bracket-metadata extraction, and prefix-based classification.
No domain validation is performed — every value is stored as a string.
"""

from __future__ import annotations
from src.models import ParsedMap
from src.parser.errors import ParseError

# parse_map(path: str) -> ParsedMap  —  YOUR TURN: replace the stub body
# below using this guide. Write the code yourself, one step at a time.
#
# GOAL: turn a map file into a ParsedMap. Any malformed content raises
# ParseError(line_number, <message>) using the REAL file line number.
#
# STRING / STRUCTURE HINTS (not the solution):
#   enumerate(file, start=1)   → (line_number, raw_line) pairs
#   raw_line.split("#", 1)[0]  → drop the comment, keep the rest
#   text.strip()               → remove surrounding whitespace
#   line.split("[", 1)[0]      → head of the line (before metadata)
#   head.split()               → whitespace tokens of the head
#
# STEP 1 — read and pre-process lines
#   Open the file and read it line by line with enumerate(start=1).
#   For each raw line:
#     a. Strip everything from '#' onward (inline comments).
#     b. Strip leading/trailing whitespace.
#     c. Skip if empty.
#   Keep every surviving line TOGETHER WITH its real line number
#   (list of (line_number, line) pairs).
#
# STEP 2 — require a first content line
#   If there are NO content lines at all (empty or comment-only file),
#   raise ParseError(1, ...) — line 1 is where 'nb_drones' belongs.
#
# STEP 3 — parse the drone count
#   The FIRST content line must be 'nb_drones: <positive int>'.
#   Split on ': ' and validate:
#     - wrong prefix or missing colon  → ParseError
#     - int() fails (abc, 1.5)        → ParseError
#     - value < 1 (0, -5)             → ParseError
#   Keep the int for the final ParsedMap.
#
# STEP 4 — process every remaining content line by prefix
#   head = line.split("[", 1)[0];  tokens = head.split()
#   prefix = tokens[0]  (e.g. 'start_hub:', 'end_hub:', 'hub:',
#   'connection:')
#   Dispatch on prefix:
#     - 'start_hub:' → parse hub, record it as start, flag start_found.
#       A SECOND start_hub → ParseError (duplicate).
#     - 'end_hub:'   → same pattern for the end hub.
#     - 'hub:'       → parse hub, append to the zones list.
#     - 'connection:'→ parse connection, append to the connections list.
#     - anything else → ParseError (unknown prefix).
#
# STEP 5 — enforce both hubs
#   After the loop, if the start hub was never found → ParseError using
#   the line number of the LAST content line. Same for the end hub.
#
# STEP 6 — build the ParsedMap
#   Return ParsedMap(nb_drones=..., start_hub=..., end_hub=...,
#   zones=..., connections=...).
#   NOTE: start_hub and end_hub are REQUIRED fields — hold them as
#   'ParsedZone | None' locals until step 5 validates them.
#
# Suggested helpers (each line-number aware; all raise ParseError):
#
#   _parse_nb_drones(line, line_number) -> int
#     Implements STEP 3 on a single line.
#
#   _parse_hub_line(line, line_number) -> ParsedZone
#     head = line.split("[", 1)[0].strip();  tokens = head.split()
#     - EXACTLY 4 tokens: [prefix, name, x, y]  else ParseError
#       (also catches missing / extra coordinates)
#     - int(x) and int(y); non-integer → ParseError
#     - metadata = _parse_metadata(line, line_number)  (already written)
#     - return ParsedZone(name=name, x=x, y=y, metadata=metadata)
#
#   _parse_connection_line(line, line_number) -> ParsedConnection
#     head = line.split("[", 1)[0].strip();  tokens = head.split()
#     - EXACTLY 2 tokens: [connection:, <A>-<B>]  else ParseError
#     - endpoints = tokens[1].split("-")
#       - exactly 2 parts AND both non-empty  else ParseError
#         (covers 'AB', 'A-B-C', 'A-', '-B')
#     - metadata = _parse_metadata(line, line_number)
#     - return ParsedConnection(zone_a=..., zone_b=..., metadata=...)


def parse_map(path: str) -> ParsedMap:
    """Parse a map file into a ParsedMap.

    Placeholder — replace the body using the guide above.
    """
    raise NotImplementedError


def _parse_metadata(raw_line: str, line_number: int) -> dict[str, str]:
    """Extract the "[key=value ...]" metadata of a map line.

    Returns an empty dict when no brackets are present. Raises
    ParseError on malformed brackets, key/value tokens, or trailing
    text after the closing bracket.
    """
    open_index = raw_line.find("[")
    close_index = raw_line.rfind("]")

    if open_index == -1 and close_index == -1:
        return {}
    elif open_index == -1 or close_index == -1:
        raise ParseError(line_number, "metadata missing '[' or ']'")
    elif open_index > close_index:
        raise ParseError(line_number, "metadata brackets out of order")
    elif raw_line[close_index + 1:].strip():
        raise ParseError(line_number, "unexpected content after ']'")

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
