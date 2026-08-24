"""Pygame-based map viewer and simulation front-end for Fly-in maps.

Hosts a ``MapViewer`` window that renders the current map as chunky
retro pixel-art on a low-res canvas. Controls are keyboard-driven: a
bottom-left legend shows the bindings, ``M`` opens the map picker, and
``SPACE``/``BACKSPACE``/``+``/``-`` drive the simulation through the
engine (play/pause, rewind, auto-play speed). Built on the parser, the
converter, the pure GUI helpers, and ``src.simulation``.
"""

from __future__ import annotations

import math
from pathlib import Path

import pygame

from src.gui.constants import SPEEDS, TOAST_DURATION_MS
from src.gui.controller import SimController
from src.gui.maps import DEFAULT_CANVAS, list_maps, load_map
from src.gui.menu import MapMenu
from src.models.drone import Drone
from src.models.enums import ZoneType
from src.models.graph import Graph
from src.models.zone import Zone
from src.palette import PALETTE, color_role
from src.simulation.engine import Simulation

_GOLDEN_ANGLE = 2.399963229063653

SCALE = 2
WINDOW = (DEFAULT_CANVAS[0] * SCALE, DEFAULT_CANVAS[1] * SCALE)

#: Height of the bottom HUD band (controls, readouts, messages).
HUD_HEIGHT = 48
#: Height of the top map band (simulation rendering area).
MAP_HEIGHT = DEFAULT_CANVAS[1] - HUD_HEIGHT

_ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
_FONT_PATH = _ASSETS_DIR / "fonts" / "PressStart2P-Regular.ttf"

_BG = PALETTE["bg"]
_GOLD = PALETTE["gold"]
_ROSE = PALETTE["rose"]
_FOAM = PALETTE["foam"]
_PINE = PALETTE["pine"]
_TEXT = PALETTE["text"]
_MUTED = PALETTE["muted"]

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

ZONE_RADIUS = 14
DRONE_RADIUS = 5
RING_WIDTH = 3

TOAST_BG = PALETTE["surface"]
LEGEND_PADDING = 4
MENU_PADDING = 10
MENU_BORDER = _ROSE


def _zone_color(zone: Zone) -> tuple[int, int, int]:
    """Return the fill color for a zone, honoring explicit colors.

    Explicit ``color=`` metadata is mapped to the rose-pine palette.
    Unknown or ``none`` falls back to the zone-type default.
    """
    if zone.color != "none":
        role = color_role(zone.color)
        if role is not None:
            return PALETTE[role]
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


class MapViewer:
    """Pygame window hosting the map and keyboard controls."""

    def __init__(
        self,
        maps_dir: str | Path,
        starting_map: str | None = None,
        canvas: tuple[int, int] = DEFAULT_CANVAS,
    ) -> None:
        self.maps_dir = Path(maps_dir)
        self.canvas = canvas
        self.map_canvas = (canvas[0], MAP_HEIGHT)
        self.current_map: str | None = None
        self.graph: Graph | None = None
        self.fleet: list[Drone] | None = None
        self.positions: dict[str, tuple[int, int]] | None = None
        self.error: str | None = None
        self.error_visible_until: int | None = None
        self.running = True
        self.menu = MapMenu(list_maps(self.maps_dir))
        self.controller = SimController()

        self.screen = self._init_window()
        self.clock = pygame.time.Clock()
        self.map_surface = pygame.Surface(canvas)
        self.font = pygame.font.Font(str(_FONT_PATH), 8)
        self.legend_font = pygame.font.Font(str(_FONT_PATH), 7)
        if not self.menu.options:
            self.error = f"No .map files found in {self.maps_dir}"
            self.error_visible_until = None
        if starting_map is not None:
            self._load_map(starting_map)

    def _init_window(self) -> pygame.Surface:
        """Initialize pygame and open a resizable window."""
        pygame.init()
        screen = pygame.display.set_mode(WINDOW, pygame.RESIZABLE)
        pygame.display.set_caption(self._caption())
        return screen

    def _caption(self) -> str:
        """Return the window caption for the current map."""
        return f"Fly-in: {self.current_map}" if self.current_map else "Fly-in"

    def _load_map(self, name: str) -> None:
        """Load a map by name, keeping the current one on failure."""
        result, message = load_map(self.maps_dir / name, self.map_canvas)
        if message is not None:
            self.error = message
            self.error_visible_until = (
                pygame.time.get_ticks() + TOAST_DURATION_MS
            )
            return
        assert result is not None
        graph, fleet, positions = result
        self.graph = graph
        self.fleet = fleet
        self.positions = positions
        self.current_map = name
        self.error = None
        self.error_visible_until = None
        self.controller.set_simulation(Simulation(graph, fleet))
        pygame.display.set_caption(self._caption())

    def _handle_event(self, event: pygame.event.Event) -> None:
        """Dispatch one pygame event."""
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            self._handle_key(event.key)
        elif event.type == pygame.VIDEORESIZE:
            self._on_resized(event.size)
        elif event.type in (
            pygame.WINDOWRESIZED,
            pygame.WINDOWSIZECHANGED,
        ):
            size = self._resize_event_size(event)
            if size is not None:
                self._on_resized(size)

    def _handle_key(self, key: int) -> None:
        """Route a keypress to the menu or the simulation controls."""
        if self.menu.visible:
            self._handle_menu_key(key)
        else:
            self._handle_sim_key(key)

    def _handle_sim_key(self, key: int) -> None:
        """Act on a simulation or overlay key."""
        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_SPACE:
            self.controller.toggle_play(self.fleet)
        elif key == pygame.K_BACKSPACE:
            fleet = self.controller.step_back(self.graph)
            if fleet is not None:
                self.fleet = fleet
        elif key in (pygame.K_PLUS, pygame.K_EQUALS):
            self.controller.speed_up()
        elif key == pygame.K_MINUS:
            self.controller.speed_down()
        elif key == pygame.K_m:
            self._toggle_map_menu()

    def _handle_menu_key(self, key: int) -> None:
        """Navigate and confirm selections in the open map menu."""
        if key in (pygame.K_ESCAPE, pygame.K_m):
            self.menu.close()
        elif key in (pygame.K_UP, pygame.K_DOWN):
            self.menu.move(1 if key == pygame.K_DOWN else -1)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._select_menu_map()

    def _toggle_map_menu(self) -> None:
        """Open the map picker with fresh options, or close it."""
        self.menu.options = list_maps(self.maps_dir)
        if self.menu.visible:
            self.menu.close()
            return
        if not self.menu.options:
            return
        if self.current_map in self.menu.options:
            self.menu.selected = self.menu.options.index(self.current_map)
        self.menu.open()

    def _select_menu_map(self) -> None:
        """Load the highlighted map and close the menu."""
        name = self.menu.current()
        if name is None:
            return
        self.menu.close()
        if name == self.current_map:
            return
        self._load_map(name)

    def _on_resized(self, size: tuple[int, int]) -> None:
        """Resize the window, ignoring events that match the screen."""
        if size == self.screen.get_size():
            return
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        pygame.display.set_caption(self._caption())

    def _resize_event_size(
        self, event: pygame.event.Event
    ) -> tuple[int, int] | None:
        """Extract the reported size from a resize event, if present."""
        attributes = event.dict
        width = attributes.get("w") or attributes.get("x")
        height = attributes.get("h") or attributes.get("y")
        if width and height:
            return (width, height)
        return None

    def _render(self) -> pygame.Surface:
        """Draw the current frame and return the window surface."""
        surface = self.map_surface
        surface.fill(_BG)
        if self.graph is not None and self.positions is not None:
            self._draw_map(surface)
        self._draw_hud(surface)
        self._draw_menu(surface)
        scaled = pygame.transform.scale(surface, self.screen.get_size())
        self.screen.blit(scaled, (0, 0))
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

    def _legend_rows(self) -> list[tuple[str, str]]:
        """Return the key legend as (key, action) rows."""
        speed = SPEEDS[self.controller.speed_index]
        rows = [
            ("SPACE", "PLAY/PAUSE"),
            ("BKSP", "STEP -1"),
            ("+/-", f"SPEED {speed:g}x"),
            ("M", "MAPS"),
        ]
        return rows

    def _hud_row_ys(self) -> tuple[int, int, int]:
        """Return the top-y of the three stacked HUD rows."""
        line_height = self.legend_font.get_height()
        gap = 4
        base = MAP_HEIGHT + LEGEND_PADDING + 4
        return (
            base,
            base + line_height + gap,
            base + 2 * (line_height + gap),
        )

    def _draw_hud(self, surface: pygame.Surface) -> None:
        """Draw the bottom HUD bar: three stacked rows."""
        width = surface.get_width()
        pygame.draw.rect(
            surface, TOAST_BG, pygame.Rect(0, MAP_HEIGHT, width, HUD_HEIGHT)
        )
        pygame.draw.line(
            surface, _MUTED, (0, MAP_HEIGHT), (width, MAP_HEIGHT), 1
        )
        y_msg, y_stat, y_ctrl = self._hud_row_ys()

        label = self.legend_font.render("Message:", True, _MUTED)
        surface.blit(label, (LEGEND_PADDING, y_msg))
        message = self.error or self.controller.status
        if message is not None:
            color = _ROSE if self.error is not None else _FOAM
            text = self.legend_font.render(message, True, color)
            surface.blit(
                text, (LEGEND_PADDING + label.get_width() + 4, y_msg)
            )

        turn = (
            self.controller.sim.state.turn
            if self.controller.sim is not None
            else 0
        )
        speed = SPEEDS[self.controller.speed_index]
        readout = f"TURN {turn}   SPEED {speed:g}x"
        surface.blit(
            self.legend_font.render(readout, True, _GOLD),
            (LEGEND_PADDING, y_stat),
        )

        controls = "   ".join(
            f"{k} {a}" for k, a in self._legend_rows()
        )
        surface.blit(
            self.legend_font.render(controls, True, _TEXT),
            (LEGEND_PADDING, y_ctrl),
        )

    def _draw_menu(self, surface: pygame.Surface) -> None:
        """Draw the map picker as a centered overlay when it is open."""
        if not self.menu.visible:
            return
        options = self.menu.options
        line_height = self.font.get_height()
        title = "SELECT MAP"
        hint = "UP/DOWN  ENTER  ESC"
        widths = [self.font.size(text)[0] for text in options]
        widths += [self.font.size(title)[0], self.font.size(hint)[0]]
        box_w = max(widths) + 2 * MENU_PADDING
        box_h = 2 * MENU_PADDING + line_height * (len(options) + 2)
        left = (surface.get_width() - box_w) // 2
        top = (surface.get_height() - box_h) // 2
        box = pygame.Rect(left, top, box_w, box_h)
        pygame.draw.rect(surface, TOAST_BG, box)
        pygame.draw.rect(surface, MENU_BORDER, box, 2)
        y = top + MENU_PADDING
        title_label = self.font.render(title, True, _GOLD)
        surface.blit(title_label, (left + MENU_PADDING, y))
        y += line_height
        for index, option in enumerate(options):
            marker = ">" if index == self.menu.selected else " "
            color = _ROSE if index == self.menu.selected else _TEXT
            label = self.font.render(f"{marker} {option}", True, color)
            surface.blit(label, (left + MENU_PADDING, y))
            y += line_height
        hint_label = self.font.render(hint, True, _MUTED)
        surface.blit(hint_label, (left + MENU_PADDING, y))

    def _toast_active(self) -> bool:
        """Whether the error toast should currently be drawn."""
        if self.error is None:
            return False
        if self.error_visible_until is None:
            return True
        return (
            pygame.time.get_ticks() < self.error_visible_until
        )

    def _prune_error(self) -> None:
        """Clear the error once its toast window has elapsed."""
        if (
            self.error is not None
            and self.error_visible_until is not None
            and pygame.time.get_ticks() >= self.error_visible_until
        ):
            self.error = None
            self.error_visible_until = None

    def _prune_status(self) -> None:
        """Clear the status message once its window has elapsed."""
        self.controller.prune_status()

    def run(self) -> None:
        """Run the frame loop until the window is closed."""
        while self.running:
            dt = self.clock.tick(30)
            self._prune_error()
            self._prune_status()
            for event in pygame.event.get():
                self._handle_event(event)
            self.controller.auto_step(dt, self.fleet)
            self._render()
            pygame.display.flip()
        pygame.quit()


def run(map_path: str) -> None:
    """Open a viewer for the map's directory and run until closed."""
    path = Path(map_path)
    viewer = MapViewer(path.parent, starting_map=path.name)
    viewer.run()
