"""Text-file scanner that produces a ``ParsedMap`` from a raw map file.

This module handles line-oriented parsing: comment stripping, token
splitting, bracket-metadata extraction, and prefix-based classification.
No domain validation is performed — every value is stored as a string.
"""

from __future__ import annotations
from src.models import ParsedConnection, ParsedMap, ParsedZone
from src.parser.errors import ParseError


def parse_map(path: str) -> ParsedMap:
    """Parse a map file into a ParsedMap.

    Any malformed content raises ParseError(line_number, <message>).
    """
    with open(path, "r", encoding="utf-8") as file:
        content_lines: list[tuple[int, str]] = []

        for line_number, raw_line in enumerate(file, start=1):
            text = raw_line.split("#", 1)[0]
            line = text.strip()
            if line:
                content_lines.append((line_number, line))

        if not content_lines:
            raise ParseError(
                1, "File is empty or contains only comments. "
                "Missing 'nb_drones'."
            )

        first_line_num, first_line = content_lines[0]
        nb_drones = _parse_nb_drones(first_line, first_line_num)

        start_hub: ParsedZone | None = None
        end_hub: ParsedZone | None = None
        zones: list[ParsedZone] = []
        connections: list[ParsedConnection] = []

        for line_number, line in content_lines[1:]:
            head = line.split("[", 1)[0].strip()
            tokens = head.split()
            if not tokens:
                raise ParseError(line_number, "line has no prefix")

            prefix = tokens[0]

            match prefix:
                case "start_hub:":
                    if start_hub is not None:
                        raise ParseError(
                            line_number, "Duplicate start_hub defined"
                        )
                    start_hub = _parse_hub_line(line, line_number)

                case "end_hub:":
                    if end_hub is not None:
                        raise ParseError(
                            line_number, "Duplicate end_hub defined"
                        )
                    end_hub = _parse_hub_line(line, line_number)

                case "hub:":
                    zones.append(_parse_hub_line(line, line_number))

                case "connection:":
                    connections.append(
                        _parse_connection_line(line, line_number)
                    )

                case _:
                    raise ParseError(
                        line_number, f"Unknown prefix '{prefix}'"
                    )

        last_line_num = content_lines[-1][0]
        if start_hub is None:
            raise ParseError(
                last_line_num, "Map is missing a required start_hub"
            )

        if end_hub is None:
            raise ParseError(
                last_line_num, "Map is missing a required end_hub"
            )

        return ParsedMap(
            nb_drones=nb_drones,
            start_hub=start_hub,
            end_hub=end_hub,
            zones=zones,
            connections=connections,
        )


def _parse_nb_drones(line: str, line_number: int) -> int:
    """Parse and validate the 'nb_drones: <int>' first line."""
    parts = line.split(": ", 1)
    if len(parts) != 2 or parts[0] != "nb_drones":
        raise ParseError(line_number, "expected 'nb_drones: <int>' line")
    try:
        value = int(parts[1])
    except ValueError:
        raise ParseError(line_number, "nb_drones must be an integer") from None
    if value < 1:
        raise ParseError(
            line_number, "nb_drones must be a positive integer"
        )
    return value


def _parse_hub_line(line: str, line_number: int) -> ParsedZone:
    """Parse a hub line (start/end/hub) into a ParsedZone."""
    head = line.split("[", 1)[0].strip()
    tokens = head.split()
    if len(tokens) != 4:
        raise ParseError(
            line_number, "hub line must be '<prefix> <name> <x> <y>'"
        )
    _, name, x_token, y_token = tokens
    try:
        x = int(x_token)
        y = int(y_token)
    except ValueError:
        raise ParseError(
            line_number, "hub coordinates must be integers"
        ) from None
    metadata = _parse_metadata(line, line_number)
    return ParsedZone(name=name, x=x, y=y, metadata=metadata)


def _parse_connection_line(line: str, line_number: int) -> ParsedConnection:
    """Parse a 'connection: <A>-<B>' line into a ParsedConnection."""
    head = line.split("[", 1)[0].strip()
    tokens = head.split()
    if len(tokens) != 2:
        raise ParseError(
            line_number, "connection line must be '<A>-<B>'"
        )
    endpoints = tokens[1].split("-")
    if len(endpoints) != 2 or not all(endpoints):
        raise ParseError(
            line_number, "connection must link exactly two zones"
        )
    metadata = _parse_metadata(line, line_number)
    return ParsedConnection(
        zone_a=endpoints[0], zone_b=endpoints[1], metadata=metadata
    )


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
