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
    "surface": (38, 35, 58),
}

#: Maps common color names (from map files) to rose-pine roles.
#: Synonyms grouped by target role. Keys are lowercase for case-insensitivity.
COLOR_NAME_TO_ROLE: dict[str, str] = {
    # reds / pinks
    "red": "rose",
    "rose": "rose",
    "pink": "rose",
    "magenta": "rose",
    "crimson": "rose",
    "darkred": "rose",
    "maroon": "rose",
    # blues / purples
    "blue": "iris",
    "iris": "iris",
    "purple": "iris",
    "violet": "iris",
    "indigo": "iris",
    "navy": "iris",
    "rainbow": "iris",
    # greens / teals
    "green": "pine",
    "pine": "pine",
    "teal": "pine",
    "lime": "pine",
    # cyans
    "cyan": "foam",
    "foam": "foam",
    "aqua": "foam",
    # yellows / oranges / browns
    "gold": "gold",
    "yellow": "gold",
    "orange": "gold",
    "amber": "gold",
    "brown": "gold",
    "olive": "gold",
    # neutrals
    "white": "text",
    "text": "text",
    "silver": "text",
    "gray": "muted",
    "grey": "muted",
    "muted": "muted",
    "black": "muted",
}

#: Roles used for deterministic fallback colors of unknown names.
_FALLBACK_ROLES: tuple[str, ...] = (
    "rose",
    "iris",
    "pine",
    "foam",
    "gold",
    "muted",
)


def color_role(color_name: str) -> str | None:
    """Map a color name to a rose-pine role, or None for 'none'.

    Lowercases the input for case-insensitive matching. Known names use
    explicit synonyms; any other single-word color gets a deterministic
    fallback role so every specified color is still visualized.

    Args:
        color_name: The color name from map metadata.

    Returns:
        A rose-pine role, or None for an empty name or ``"none"``.
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
