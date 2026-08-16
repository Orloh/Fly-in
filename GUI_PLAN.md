# GUI_PLAN.md — Retro pixel-art GUI for Fly-in

A roadmap for the graphical layer of Fly-in: the widget set, the visual
style, and the technologies behind it. Supersedes the earlier "add a
simple pygame window" idea — the GUI is now a first-class landing pad
for the future simulation controls.

## Main idea

One window that renders the current map as chunky retro pixel-art and
hosts a compact control bar of pygame-gui widgets. The map layer is
kept visually separate from the UI layer (scale/resolution differ), but
the whole frame shares one rose-pine palette and one pixel font so it
reads as a single cohesive arcade look.

Current milestone: the **map selector** dropdown. Play/pause, step-back,
and velocity controls are planned and outlined below; they slot into the
same widget factory with no rework.

## Libraries and technologies

| Piece | Choice | Why |
|---|---|---|
| Rendering | `pygame-ce` (drop-in for `pygame`) | Frame-based animation, simple draw primitives |
| Widgets | `pygame-gui` (add via `uv add pygame-gui`) | Buttons, dropdown, slider, themes — battle-tested, one `UIManager` |
| Fonts | `pygame-gui` theme + bundled TTF | **Press Start 2P** (SIL OFL-1.1), vendored under `assets/fonts/` with the license |
| Theme | JSON theme file `assets/theme.json` | Colors/fonts centralized, widgets restyle in one place |
| Layout math | Pure helpers in `src/gui/` (`transform.layout`, `maps.list_maps`) | Testable without pygame |

Frameworks considered and rejected: `pygame-menu` (menu-screen oriented,
not an in-game HUD paradigm) and `pygame-widgets` (lighter but less robust).

## Style and themes

- **Palette:** rose-pine. bg `#191724`, gold `#f6c177`, rose `#eb6f92`,
  foam `#9ccfd8`, iris `#c4a7e7`, pine `#31748f`, text `#e0def4`.
- **Pixel-art map:** draw the map to a low-res canvas
  (`VIRTUAL = 640 × 360`), upscale to the window (`1280 × 720`,
  `SCALE = 2`) with `pygame.transform.scale` — nearest-neighbor, so
  pixels stay crisp and chunky. Every map pixel becomes a solid 2×2 block.
- **Crisp UI:** pygame-gui text upscales *fuzzily* through
  `transform.scale`, so the UI layer is drawn at **native window
  resolution** on top of the scaled map (Minecraft approach). This also
  sidesteps mouse-coordinate scaling entirely.
- **Font:** Press Start 2P for UI text and map labels; small sizes
  (≈8–10px) on the low-res map canvas.
- **Widgets:** flat, blocky shapes (thin borders, no shadows) so the UI
  matches the chunky map instead of fighting it.

## Controls (planned, all pygame-gui)

Widgets are created in one central factory in `app.py` so each control
below is an additive change. Play/pause, step-back, and velocity await
the simulation engine; the map selector is the shipped milestone.

| Control | Widget | Behaviour |
|---|---|---|
| Map selector | `UIDropDownMenu`, bottom-left, `expand_direction="up"` | Options = `list_maps(maps_dir)`. Reloads the map on change; parse/IO failure shows an error line and keeps the current map |
| Play / Pause | `UIButton` (toggling) | Starts / pauses the simulation loop |
| Step-back | `UIButton` | Rewinds the simulation by one time step |
| Velocity | `UIHorizontalSlider` | Scales simulated time (e.g. 0.25×–4×) in real time |
| Keyboard | raw pygame events | Nice-to-have: `Space` = play/pause, `←` = step-back — mirrors the buttons |

## Layout / architecture

```
src/gui/
  app.py        # pygame window, UIManager, widget factory, frame loop
  maps.py       # pure: list_maps() -> sorted *.map names
  transform.py  # pure: world coords -> low-res canvas pixels (layout)
assets/
  theme.json    # rose-pine palette + Press Start 2P font config
  fonts/        # PressStart2P-Regular.ttf + OFL.txt
tests/
  test_gui_maps.py, test_gui_transform.py   # pure logic
```

Frame loop (per tick):

1. Pull pygame events; `QUIT`/`ESC` exits.
2. `manager.process_events` (dropdown clicks handled here).
3. `manager.update(dt)` with `dt = clock.tick(30) / 1000`.
4. Draw map onto the 640 × 360 canvas (rose-pine palette, pixel font).
5. `pygame.transform.scale(canvas, WINDOW)` → blit to the screen.
6. `manager.draw_ui(screen)` at native resolution → `flip()`.

## Dependencies to add / config

- `uv add pygame-gui` (resolved to **pygame-ce** 2.5.8 — pygame-gui
  0.6.14 requires it. Replaced classic `pygame` in `pyproject.toml`;
  pygame-ce is a drop-in for the `pygame` module).
- `pyproject.toml`: mypy override `pygame_gui.*` →
  `ignore_missing_imports = true` (same pattern as `pygame.*`).
- Vendor `PressStart2P-Regular.ttf` + the OFL license in `assets/fonts/`.

## Milestones

1. **Map selector (current)** — dropdown, `list_maps`, error handling,
   low-res map rendering, rose-pine theme + pixel font. [in progress]
2. **Simulation GUI controls** — play/pause + step-back buttons,
   velocity slider; wiring once the simulation engine exists.
3. **Polish** — keyboard shortcuts, drone animation states, per-zone
   accents/status dots.