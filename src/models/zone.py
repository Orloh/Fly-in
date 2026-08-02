"""Zone model representing a single node in the routing graph."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.models.enums import ZoneType


class Zone(BaseModel):
    """A node in the map graph.

    The start_hub and end_hub are modeled with boolean flags rather than
    subclasses, keeping parsing and traversal code paths uniform. Their
    only behavioural difference is an unlimited occupancy capacity.
    """

    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    color: str = "none"
    max_drones: int = Field(default=1, ge=1)
    is_start_hub: bool = False
    is_end_hub: bool = False

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if "-" in value or " " in value:
            raise ValueError(
                "zone names cannot contain dashes or spaces"
            )
        return value

    @property
    def capacity(self) -> int | None:
        """Occupancy limit, or None for hubs (unlimited)."""
        if self.is_start_hub or self.is_end_hub:
            return None
        return self.max_drones
