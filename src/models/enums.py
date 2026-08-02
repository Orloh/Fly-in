"""Enumerations used across the Fly-in simulation models."""

from __future__ import annotations

from enum import Enum


class ZoneType(str, Enum):
    """Movement cost semantics of a zone."""

    NORMAL = "normal"
    PRIORITY = "priority"
    RESTRICTED = "restricted"
    BLOCKED = "blocked"


class DroneStatus(str, Enum):
    """Runtime status of a drone."""

    WAITING = "waiting"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    BLOCKED = "blocked"
