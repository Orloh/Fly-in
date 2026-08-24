"""Shared rose-pine palette for CLI (ANSI) and GUI (RGB).

Single source of truth for zone-name color mapping across both layers.
No pygame dependency — pure data and helpers.
"""

from __future__ import annotations

#: Rose-pine truecolor palette (r, g, b). Canonical roles.
PALETTE: dict[str, tuple[int, int, int]] = {
    "gold": (246, 193, 119),
    "foam": (156, 207, 216),
    "rose": (235, 111, 146),
    "pine": (49, 116, 143),
    "iris": (196, 167, 231),
    "text": (224, 222, 244),
    "muted": (110, 106, 134),
    "bg": (25, 23, 36),
}

#: Maps common color names (from map files) to rose-pine roles.
#: Synonyms grouped by target role. Keys are lowercase for case-insensitivity.
COLOR_NAME_TO_ROLE: dict[str, str] = {
    # reds / pinks
    "red": "rose",
    "rose": "rose",
    "pink": "rose",
    "magenta": "rose",
    # blues / purples
    "blue": "iris",
    "iris": "iris",
    "purple": "iris",
    "violet": "iris",
    "indigo": "iris",
    # greens / teals
    "green": "pine",
    "pine": "pine",
    "teal": "pine",
    # cyans
    "cyan": "foam",
    "foam": "foam",
    "aqua": "foam",
    # yellows / oranges
    "gold": "gold",
    "yellow": "gold",
    "orange": "gold",
    "amber": "gold",
    # neutrals
    "white": "text",
    "text": "text",
    "gray": "muted",
    "grey": "muted",
    "muted": "muted",
    "black": "muted",
}


def color_role(color_name: str) -> str | None:
    """Map a color name to a rose-pine role, or None for 'none'/unknown.

    Lowercases the input for case-insensitive matching.
    """
    if not color_name:
        return None
    key = color_name.strip().lower()
    if key == "none":
        return None
    return COLOR_NAME_TO_ROLE.get(key)
