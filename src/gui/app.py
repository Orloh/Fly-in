"""Pygame-based map viewer for loaded Fly-in maps.

Hosts a ``MapViewer`` window that renders the current map as chunky
retro pixel-art on a low-res canvas and offers a pygame-gui dropdown to
switch maps. Decoupled from the simulation engine: it only depends on
the parser, the converter, and the pure GUI helpers.
"""

from __future__ import annotations

import math
from pathlib import Path

import pygame
from pygame_gui import UI_DROP_DOWN_MENU_CHANGED, UIManager
from pygame_gui.elements import UIDropDownMenu

from src.gui.maps import DEFAULT_CANVAS, list_maps, load_map
from src.models.drone import Drone
from src.models.enums import ZoneType
from src.models.graph import Graph
from src.models.zone import Zone

_GOLDEN_ANGLE = 2.399963229063653

SCALE = 2
WINDOW = (DEFAULT_CANVAS[0] * SCALE, DEFAULT_CANVAS[1] * SCALE)

_ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
_THEME_PATH = _ASSETS_DIR / "theme.json"
_FONT_PATH = _ASSETS_DIR / "fonts" / "PressStart2P-Regular.ttf"

_BG = (25, 23, 36)
_GOLD = (246, 193, 119)
_ROSE = (235, 111, 146)
_FOAM = (156, 207, 216)
_PINE = (49, 116, 143)
_TEXT = (224, 222, 244)
_MUTED = (110, 106, 134)

ZONE_COLORS = {
    ZoneType.NORMAL: _FOAM,
    ZoneType.PRIORITY: _GOLD,
    ZoneType.RESTRICTED: _ROSE,
    ZoneType.BLOCKED: _MUTED,
}

LINE_COLOR = _PINE
LABEL_COLOR = _TEXT
DRONE_COLOR = _GOLD
DRONE_RING = _MUTED
START_RING = _PINE
END_RING = _ROSE
ERROR_COLOR = _ROSE

ZONE_RADIUS = 14
DRONE_RADIUS = 5
RING_WIDTH = 3

TOAST_DURATION_MS = 5000
TOAST_MARGIN = 12
TOAST_PADDING = 10
TOAST_BORDER_WIDTH = 2
TOAST_BG = (38, 35, 58)
TOAST_BORDER = _ROSE

DROPDOWN_MARGIN = 12
DROPDOWN_WIDTH = 220
DROPDOWN_HEIGHT = 30


def _parse_color(name: str) -> tuple[int, int, int]:
    """Convert a color name or CSS value into an RGB triple."""
    try:
        color = pygame.Color(name)
    except ValueError:
        return (200, 200, 200)
    return (color.r, color.g, color.b)


def _zone_color(zone: Zone) -> tuple[int, int, int]:
    """Return the fill color for a zone, honoring explicit colors."""
    if zone.color != "none":
        return _parse_color(zone.color)
    return ZONE_COLORS[zone.zone_type]


def _draw_connections(
    surface: pygame.Surface,
    positions: dict[str, tuple[int, int]],
    graph: Graph,
) -> None:
    """Draw every connection as a line between zone centers."""
    for zone_a, zone_b in graph.connections:
        start = positions[zone_a]
        end = positions[zone_b]
        pygame.draw.line(surface, LINE_COLOR, start, end, 2)


def _draw_zones(
    surface: pygame.Surface,
    positions: dict[str, tuple[int, int]],
    graph: Graph,
) -> None:
    """Draw each zone as a colored circle with a ring on the hubs."""
    for name, zone in graph.zones.items():
        center = positions[name]
        pygame.draw.circle(surface, _zone_color(zone), center, ZONE_RADIUS)
        if zone.is_start_hub:
            pygame.draw.circle(
                surface, START_RING, center, ZONE_RADIUS, RING_WIDTH
            )
        elif zone.is_end_hub:
            pygame.draw.circle(
                surface, END_RING, center, ZONE_RADIUS, RING_WIDTH
            )


def _draw_labels(
    surface: pygame.Surface,
    font: pygame.font.Font,
    positions: dict[str, tuple[int, int]],
) -> None:
    """Render zone names above their circles."""
    for name, (px, py) in positions.items():
        label = font.render(name, True, LABEL_COLOR)
        surface.blit(
            label, (px - label.get_width() // 2, py - ZONE_RADIUS - 18)
        )


def _draw_drones(
    surface: pygame.Surface,
    positions: dict[str, tuple[int, int]],
    drones: list[Drone],
) -> None:
    """Draw each drone as a small ringed circle near its current zone."""
    for index, drone in enumerate(drones):
        if drone.current_zone is None:
            continue
        if drone.current_zone not in positions:
            continue
        px, py = positions[drone.current_zone]
        dx = round(8 * math.cos(index * _GOLDEN_ANGLE))
        dy = round(8 * math.sin(index * _GOLDEN_ANGLE))
        center = (px + dx, py + dy)
        pygame.draw.circle(surface, DRONE_COLOR, center, DRONE_RADIUS)
        pygame.draw.circle(surface, DRONE_RING, center, DRONE_RADIUS, 1)


def _wrap_text(
    font: pygame.font.Font, text: str, max_width: int
) -> list[str]:
    """Split ``text`` into lines that fit ``max_width`` pixels."""
    lines: list[str] = []
    for raw in text.splitlines() or [""]:
        words = raw.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


class MapViewer:
    """Pygame window hosting the map and the map-selector dropdown."""

    def __init__(
        self,
        maps_dir: str | Path,
        starting_map: str | None = None,
        canvas: tuple[int, int] = DEFAULT_CANVAS,
    ) -> None:
        self.maps_dir = Path(maps_dir)
        self.canvas = canvas
        self.current_map: str | None = None
        self.graph: Graph | None = None
        self.fleet: list[Drone] | None = None
        self.positions: dict[str, tuple[int, int]] | None = None
        self.error: str | None = None
        self.error_visible_until: int | None = None
        self.running = True

        self.screen = self._init_window()
        self.clock = pygame.time.Clock()
        self.map_surface = pygame.Surface(canvas)
        self.manager = UIManager(
            self.screen.get_size(),
            theme_path=str(_THEME_PATH),
            enable_live_theme_updates=False,
        )
        self.font = pygame.font.Font(str(_FONT_PATH), 8)
        self.dropdown = self._build_ui(starting_map)
        if starting_map is not None:
            self._load_map(starting_map)

    def _init_window(self) -> pygame.Surface:
        """Initialize pygame and open the scaled-up window."""
        pygame.init()
        window = (self.canvas[0] * SCALE, self.canvas[1] * SCALE)
        screen = pygame.display.set_mode(window, pygame.RESIZABLE)
        pygame.display.set_caption("Fly-in")
        return screen

    def _build_ui(self, starting_map: str | None) -> UIDropDownMenu | None:
        """Create the map-selector dropdown, or None with an error."""
        options = list_maps(self.maps_dir)
        if not options:
            self.error = f"No .map files found in {self.maps_dir}"
            self.error_visible_until = None
            return None
        starting = starting_map if starting_map in options else options[0]
        rect = pygame.Rect(
            (
                DROPDOWN_MARGIN,
                self.screen.get_height() - DROPDOWN_MARGIN - DROPDOWN_HEIGHT,
            ),
            (DROPDOWN_WIDTH, DROPDOWN_HEIGHT),
        )
        return UIDropDownMenu(
            options,
            starting,
            rect,
            manager=self.manager,
            expansion_height_limit=120,
        )

    def _load_map(self, name: str) -> None:
        """Load a map by name, keeping the current one on failure."""
        result, message = load_map(self.maps_dir / name, self.canvas)
        if message is not None:
            self.error = message
            self.error_visible_until = (
                pygame.time.get_ticks() + TOAST_DURATION_MS
            )
            return
        assert result is not None
        self.graph, self.fleet, self.positions = result
        self.current_map = name
        self.error = None
        self.error_visible_until = None
        pygame.display.set_caption(f"Fly-in: {name}")

    def _on_map_selected(self, event: pygame.event.Event) -> None:
        """React to a new dropdown selection, ignoring no-ops."""
        if self.dropdown is None:
            return
        name = event.text
        if name == self.current_map:
            return
        self._load_map(name)

    def _handle_event(self, event: pygame.event.Event) -> None:
        """Dispatch one pygame or pygame-gui event."""
        if event.type == pygame.QUIT:
            self.running = False
        elif (
            event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
        ):
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            self._on_window_resized(event.size)
        elif event.type == pygame.WINDOWSIZECHANGED:
            self._on_window_resized((event.w, event.h))
        elif event.type == UI_DROP_DOWN_MENU_CHANGED:
            self._on_map_selected(event)
        else:
            self.manager.process_events(event)

    def _on_window_resized(self, size: tuple[int, int]) -> None:
        """Recreate the window and re-anchor the UI at a new size."""
        if size == self.screen.get_size():
            return
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.manager.set_window_resolution(size)
        if self.dropdown is not None:
            self.dropdown.set_relative_position(
                (
                    DROPDOWN_MARGIN,
                    size[1] - DROPDOWN_MARGIN - DROPDOWN_HEIGHT,
                )
            )
        caption = (
            f"Fly-in: {self.current_map}" if self.current_map else "Fly-in"
        )
        pygame.display.set_caption(caption)

    def _render(self) -> pygame.Surface:
        """Draw the current frame and return the window surface."""
        surface = self.map_surface
        surface.fill(_BG)
        if self.graph is not None and self.positions is not None:
            self._draw_map(surface)
        if self._toast_active():
            self._draw_toast(surface)
        scaled = pygame.transform.scale(surface, self.screen.get_size())
        self.screen.blit(scaled, (0, 0))
        self.manager.draw_ui(self.screen)
        return self.screen

    def _draw_map(self, surface: pygame.Surface) -> None:
        """Draw connections, labels, zones, and drones onto the canvas."""
        assert self.graph is not None
        assert self.positions is not None
        _draw_connections(surface, self.positions, self.graph)
        _draw_labels(surface, self.font, self.positions)
        _draw_zones(surface, self.positions, self.graph)
        if self.fleet is not None:
            _draw_drones(surface, self.positions, self.fleet)

    def _toast_active(self) -> bool:
        """Whether the error toast should currently be drawn."""
        if self.error is None:
            return False
        if self.error_visible_until is None:
            return True
        return pygame.time.get_ticks() < self.error_visible_until

    def _draw_toast(self, surface: pygame.Surface) -> None:
        """Draw the error message in a bottom-centered box."""
        assert self.error is not None
        text_width = surface.get_width() - 2 * (
            TOAST_MARGIN + TOAST_PADDING
        )
        lines = _wrap_text(self.font, self.error, text_width)
        line_height = self.font.get_height()
        box_w = surface.get_width() - 2 * TOAST_MARGIN
        box_h = 2 * TOAST_PADDING + line_height * len(lines)
        left = TOAST_MARGIN
        top = surface.get_height() - TOAST_MARGIN - box_h

        box = pygame.Rect(left, top, box_w, box_h)
        pygame.draw.rect(surface, TOAST_BG, box)
        pygame.draw.rect(
            surface, TOAST_BORDER, box, TOAST_BORDER_WIDTH
        )
        y = top + TOAST_PADDING
        for line in lines:
            label = self.font.render(line, True, ERROR_COLOR)
            surface.blit(label, (left + TOAST_PADDING, y))
            y += line_height

    def _prune_error(self) -> None:
        """Clear the error once its toast window has elapsed."""
        if (
            self.error is not None
            and self.error_visible_until is not None
            and pygame.time.get_ticks() >= self.error_visible_until
        ):
            self.error = None
            self.error_visible_until = None

    def run(self) -> None:
        """Run the frame loop until the window is closed."""
        while self.running:
            dt = self.clock.tick(30) / 1000.0
            self._prune_error()
            for event in pygame.event.get():
                self._handle_event(event)
            self.manager.update(dt)
            self._render()
            pygame.display.flip()
        pygame.quit()


def run(map_path: str) -> None:
    """Open a viewer for the map's directory and run until closed."""
    path = Path(map_path)
    viewer = MapViewer(path.parent, starting_map=path.name)
    viewer.run()
