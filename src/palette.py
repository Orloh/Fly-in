"""Shared Google-colored palette for the terminal CLI.

No rendering dependency: this module is pure data and helpers.
"""

from __future__ import annotations

#: Google brand-inspired truecolor palette.
PALETTE: dict[str, tuple[int, int, int]] = {
    "blue": (66, 133, 244),
    "red": (234, 67, 53),
    "yellow": (251, 188, 5),
    "green": (52, 168, 83),
    "gray": (95, 99, 104),
    "light": (241, 243, 244),
    "white": (255, 255, 255),
    "dark": (32, 33, 36),
}

#: Maps common map-file color names to Google palette roles.
COLOR_NAME_TO_ROLE: dict[str, str] = {
    "red": "red",
    "rose": "red",
    "pink": "red",
    "magenta": "red",
    "crimson": "red",
    "darkred": "red",
    "maroon": "red",
    "blue": "blue",
    "cyan": "blue",
    "aqua": "blue",
    "purple": "blue",
    "violet": "blue",
    "indigo": "blue",
    "navy": "blue",
    "green": "green",
    "lime": "green",
    "teal": "green",
    "yellow": "yellow",
    "gold": "yellow",
    "orange": "yellow",
    "amber": "yellow",
    "brown": "yellow",
    "olive": "yellow",
    "white": "white",
    "light": "light",
    "gray": "gray",
    "grey": "gray",
    "silver": "gray",
    "black": "gray",
}

#: Roles used for deterministic fallback colors of unknown names.
_FALLBACK_ROLES: tuple[str, ...] = (
    "blue",
    "red",
    "yellow",
    "green",
    "gray",
)


def color_role(color_name: str) -> str | None:
    """Map a color name to a Google palette role, or None for 'none'.

    Args:
        color_name: The color name from map metadata.

    Returns:
        A Google palette role, or None for an empty name or ``"none"``.
    """
    if not color_name:
        return None
    key = color_name.strip().lower()
    if not key or key == "none":
        return None
    explicit = COLOR_NAME_TO_ROLE.get(key)
    if explicit is not None:
        return explicit
    checksum = sum(ord(character) for character in key)
    return _FALLBACK_ROLES[checksum % len(_FALLBACK_ROLES)]
