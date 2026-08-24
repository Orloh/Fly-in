"""Connection model representing a bidirectional edge in the graph."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.graph_utils import canonical_key


class Connection(BaseModel):
    """A bidirectional link between two zones.

    Directions are canonicalized so that ``a-b`` and ``b-a`` normalize to
    the same key, enabling duplicate detection and symmetric capacity checks.
    """

    zone_a: str
    zone_b: str
    max_link_capacity: int = Field(default=1, ge=1)

    @property
    def key(self) -> tuple[str, str]:
        """Canonical (sorted) key identifying this undirected edge."""
        return canonical_key(self.zone_a, self.zone_b)

    def other(self, zone_name: str) -> str:
        """Return the endpoint opposite to ``zone_name``."""
        if zone_name == self.zone_a:
            return self.zone_b
        return self.zone_a
