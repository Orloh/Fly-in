"""Shared graph utilities.

Small pure helpers to avoid duplication across connection,
graph, engine, and tests.
"""

from __future__ import annotations


def canonical_key(a: str, b: str) -> tuple[str, str]:
    """Return the canonical (sorted) key for an undirected edge.

    Ensures ``(a, b)`` and ``(b, a)`` produce the same key.
    """
    return (a, b) if a <= b else (b, a)
