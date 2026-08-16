"""Pygame-based map renderer for loaded Fly-in maps.

Runs an event loop that draws zones, connections, and drones from a
parsed map. Decoupled from the simulation engine: it only depends on
the parser, the converter, and the pure layout helper.
"""

from __future__ import annotations

import math

import pygame

from src.gui.transform import layout
from src.models.drone import Drone
from src.models.enums import ZoneType
from src.models.graph import Graph
from src.models.zone import Zone
from src.parser.converter import build_graph
from src.parser.parser import parse_map

_GOLDEN_ANGLE = 2.399963229063653

DEFAULT_COLORS = {
    ZoneType.NORMAL: (100, 150, 220),
    ZoneType.PRIORITY: (230, 200, 60),
    ZoneType.RESTRICTED: (220, 120, 60),
    ZoneType.BLOCKED: (120, 120, 120),
}

LINE_COLOR = (180, 180, 180)
LABEL_COLOR = (30, 30, 30)
DRONE_COLOR = (240, 240, 240)
DRONE_RING = (60, 60, 60)
START_RING = (40, 180, 70)
END_RING = (220, 60, 60)
BACKGROUND = (245, 245, 245)

ZONE_RADIUS = 14
DRONE_RADIUS = 5
RING_WIDTH = 3


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
    return DEFAULT_COLORS[zone.zone_type]


def _draw_connections(
    screen: pygame.Surface,
    positions: dict[str, tuple[int, int]],
    graph: Graph,
) -> None:
    """Draw every connection as a line between zone centers."""
    for zone_a, zone_b in graph.connections:
        start = positions[zone_a]
        end = positions[zone_b]
        pygame.draw.line(screen, LINE_COLOR, start, end, 2)


def _draw_zones(
    screen: pygame.Surface,
    positions: dict[str, tuple[int, int]],
    graph: Graph,
) -> None:
    """Draw each zone as a colored circle with a ring on the hubs."""
    for name, zone in graph.zones.items():
        center = positions[name]
        pygame.draw.circle(screen, _zone_color(zone), center, ZONE_RADIUS)
        if zone.is_start_hub:
            pygame.draw.circle(
                screen, START_RING, center, ZONE_RADIUS, RING_WIDTH
            )
        elif zone.is_end_hub:
            pygame.draw.circle(
                screen, END_RING, center, ZONE_RADIUS, RING_WIDTH
            )


def _draw_labels(
    screen: pygame.Surface,
    font: pygame.font.Font,
    positions: dict[str, tuple[int, int]],
) -> None:
    """Render zone names above their circles."""
    for name, (px, py) in positions.items():
        label = font.render(name, True, LABEL_COLOR)
        screen.blit(
            label, (px - label.get_width() // 2, py - ZONE_RADIUS - 18)
        )


def _draw_drones(
    screen: pygame.Surface,
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
        pygame.draw.circle(screen, DRONE_COLOR, center, DRONE_RADIUS)
        pygame.draw.circle(
            screen, DRONE_RING, center, DRONE_RADIUS, 1
        )


def run(map_path: str, width: int = 900, height: int = 600) -> None:
    """Render a map file in a pygame window until it is closed."""
    parsed = parse_map(map_path)
    graph, drones = build_graph(parsed)
    points = {
        name: (float(zone.x), float(zone.y))
        for name, zone in graph.zones.items()
    }
    positions = layout(points, width, height)

    pygame.init()
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"Fly-in: {map_path}")
    font = pygame.font.SysFont("arial", 14)

    running = True
    clock = pygame.time.Clock()
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_ESCAPE
            ):
                running = False

        screen.fill(BACKGROUND)
        _draw_connections(screen, positions, graph)
        _draw_labels(screen, font, positions)
        _draw_zones(screen, positions, graph)
        _draw_drones(screen, positions, drones)

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
