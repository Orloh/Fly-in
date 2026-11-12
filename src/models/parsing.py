"""Parsing-layer models mirroring the raw input file structure.

These models store metadata verbatim (as strings) so the parser stays
decoupled from domain validation. Conversion to domain models happens
in a separate step.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.aliases import LineNumber, Metadata, ZoneName


class ParsedZone(BaseModel):
    """A zone line as read from the map file."""

    name: ZoneName
    x: int
    y: int
    metadata: Metadata = Field(default_factory=dict)
    line_number: LineNumber


class ParsedConnection(BaseModel):
    """A connection line as read from the map file."""

    zone_a: ZoneName
    zone_b: ZoneName
    metadata: Metadata = Field(default_factory=dict)
    line_number: LineNumber


class ParsedMap(BaseModel):
    """The full set of entities found in a map file."""

    nb_drones: int
    start_hub: ParsedZone
    end_hub: ParsedZone
    zones: list[ParsedZone] = Field(default_factory=list)
    connections: list[ParsedConnection] = Field(default_factory=list)
