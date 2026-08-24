"""Shared constants for the GUI layer.

Extracted from app.py to avoid circular imports between
app.py and controller.py.
"""

from __future__ import annotations

#: Simulation speed multipliers for auto-play.
SPEEDS = (0.5, 1.0, 2.0, 4.0)

#: How long toast/status messages remain visible (milliseconds).
TOAST_DURATION_MS = 5000
