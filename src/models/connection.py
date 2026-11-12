"""Connection model representing a bidirectional edge in the graph."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.aliases import ConnectionKey, ZoneName
from src.models.graph_utils import canonical_key


class Connection(BaseModel):
    """A bidirectional link between two zones.

    Directions are canonicalized so that ``a-b`` and ``b-a`` normalize to
    the same key, enabling duplicate detection and symmetric capacity checks.
    """

    zone_a: ZoneName
    zone_b: ZoneName
    max_link_capacity: int = Field(default=1, ge=1)

    @property
    def key(self) -> ConnectionKey:
        """Canonical (sorted) key identifying this undirected edge.

        Returns:
            The canonical ``(a, b)`` key with ``a <= b``.
        """
        return canonical_key(self.zone_a, self.zone_b)
