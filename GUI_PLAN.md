# GUI_PLAN.md — Retro pixel-art GUI for Fly-in

A roadmap for the graphical layer of Fly-in: the visual style, the
keyboard-driven controls, and the technologies behind it. Supersedes
the earlier "add a simple pygame window" idea — the GUI is now a
first-class landing pad for the future simulation controls.

## Main idea

One window that renders the current map as chunky retro pixel-art with
all controls on the keyboard — no mouse widgets. The map, a bottom HUD
bar (controls + messages + readouts), the map picker, and overlays are
all drawn to a low-res canvas and upscaled, so the whole frame reads as
one cohesive arcade look in a single rose-pine palette and one pixel font.

Shipped milestones: the **map picker** (keyboard-driven), **pathfinding**
(`dist_to_goal` + `find_path_timed` in `src/simulation/pathfinding.py` —
see `CBS_PLAN.md`), the **simulation engine** (`Simulation` in
`src/simulation/engine.py`, schedule-replay over a CBS plan), and the
**GUI controls** wired to it — `←`/`→` step back/forward (snapshot
history), driving `Simulation.step()` turn by turn.

## Libraries and technologies

| Piece | Choice | Why |
|---|---|---|
| Rendering | `pygame-ce` (drop-in for `pygame`) | Frame-based animation, simple draw primitives |
| Fonts | Bundled TTF | **Press Start 2P** (SIL OFL-1.1), vendored under `assets/fonts/` with the license |
| Palette | Rose-pine as code constants in `app.py` | bg/gold/rose/foam/pine/text — no theme file needed |
| Layout math | Pure helpers in `src/gui/` (`transform.layout`, `maps.list_map_folders`, `menu.MapMenu`) | Testable without pygame |

`pygame-gui` was evaluated for widgets and dropped: all controls are
keyboard-driven, so hand-drawn overlays on the pixel canvas match the
retro aesthetic better than any widget set.

## Style and themes

- **Palette:** rose-pine. bg `#191724`, gold `#f6c177`, rose `#eb6f92`,
  foam `#9ccfd8`, iris `#c4a7e7`, pine `#31748f`, text `#e0def4`.
- **Pixel-art map:** draw the map to a low-res canvas
  (`VIRTUAL = 640 × 360`), upscale to the window (`1280 × 720`,
  `SCALE = 2`) with `pygame.transform.scale` — nearest-neighbor, so
  pixels stay crisp and chunky. Every map pixel becomes a solid 2×2 block.
- **UI on the same canvas:** the map, a bottom HUD band, the picker, and
  overlays are drawn on the low-res canvas too, so they inherit the chunky
  look and scale with the map on resize (no native-res layer). The canvas
  is partitioned vertically: the **map band** (top, height `MAP_HEIGHT`)
  holds the simulation; the **HUD band** (bottom, `HUD_HEIGHT` ≈ 48px)
  holds controls, readouts, and messages, separated by a divider line.
  Zone layout uses the map-band height so nothing hides behind the HUD.
- **Font:** Press Start 2P for UI text and map labels; small sizes
  (≈8–10px) on the low-res map canvas.
- **Overlays:** flat, blocky boxes (thin borders, no shadows) so the UI
  matches the chunky map instead of fighting it.

## Controls (all keyboard)

| Key | Scope | Behaviour |
|---|---|---|
| `→` | global | Step forward one turn (drives `Simulation.step()`) |
| `←` | global | Step back one turn (snapshot history) |
| `T` | global | Toggle zone-name labels on/off |
| `M` | global | Toggle the map picker (folder list refreshed on open) |
| `↑` / `↓` | picker | Move the highlighted folder/map |
| `ENTER` | picker | Open the highlighted folder; load the highlighted map |
| `ESC` | picker / global | Back up to the folder list; close the picker at the top; quit when the picker is closed |
| `Ctrl+C` | global | Quit like `ESC` (terminal `SIGINT` exits 130 after a clean `pygame.quit()`) |

The bottom **HUD bar** (`_draw_hud`) shows three stacked rows:
line 1 `Message: {turn message}` (label muted, text foam=info / rose=error),
line 2 `Turn N` (or `READY` before the first step), line 3 the key
bindings. The **map picker**
(`_draw_menu`) is a centered overlay on the `MapMenu` state machine with
two-level navigation: the root lists map folders (`maps/easy`,
`maps/medium`, `maps/hard`, `maps/challenger`, `personal`); `ENTER`
descends into a folder (`MapMenu.descend`), `ESC` ascends back to the
folder list (`MapMenu.ascend`), and `ENTER` on a map loads it;
parse/IO failures surface in the HUD bar (persistent when `maps/` is
empty). The `←` rewind restores the exact turn snapshot — deep-copied
fleet *and* the message shown for that turn — then rebuilds the sim
with `replan=False` so a resumed run replays the original plan turn for
turn (deterministic makespan, no extra turns on re-simulation).

## Layout / architecture

```
src/gui/
  app.py        # MapViewer class: window, key routing, drawing, loop
  maps.py       # pure: list_map_folders + list_maps_in_folder + resolve_maps_root + load_map
  menu.py       # pure: MapMenu state machine (options, selection, open)
  transform.py  # pure: world coords -> low-res canvas pixels (layout)
assets/
  fonts/        # PressStart2P-Regular.ttf + OFL.txt
tests/
  conftest.py   # SDL dummy drivers (headless GUI tests)
  test_gui_app.py, test_gui_maps.py, test_gui_menu.py,
  test_gui_transform.py
```

Frame loop (`MapViewer.run`, per tick):

1. Pull pygame events; `QUIT` and `ESC` (picker closed) stop the loop.
   `KEYDOWN` events route through `_handle_key`: the picker owns
   `↑`/`↓`/`ENTER`/`ESC`/`M` while open; otherwise the sim keys
   (`←`, `→`, `M`) apply.
 2. Draw the map onto the top band of the 640 × 360 canvas (rose-pine
    palette, pixel font), then the bottom HUD bar (controls, readouts,
    message), and the picker overlay. In-transit drones are drawn along
    their connection, interpolated by hop progress (`_in_transit_fraction`)
    and stacked perpendicular to it per link (`_perpendicular_offset`), so
    restricted crossings visibly sit mid-link — with same-link drones in
    lanes across the connection (see `maps/personal/multi_lane.txt`).
3. `pygame.transform.scale(canvas, screen.get_size())` → blit → `flip()`.
   Load errors appear as a 5s top-center toast and the previous map
   stays current; empty `maps/` keeps a persistent toast.

Window: opens at `1280 × 720` with `pygame.RESIZABLE` and **stretches
to fill** on resize. `VIDEORESIZE` uses `event.size`;
`WINDOWRESIZED`/`WINDOWSIZECHANGED` read `w`/`h` (pygame-ce puts the
size in `x`/`y` for `WINDOWSIZECHANGED`). Same-size events are ignored
(loop guard). Because every overlay lives on the canvas, nothing is
re-laid-out when the window changes.

## Dependencies / config

- Rendering only: `pygame-ce` (drop-in for `pygame`). No widget library.
- `pyproject.toml`: mypy override `pygame.*` →
  `ignore_missing_imports = true`.
- Shipped: `assets/fonts/PressStart2P-Regular.ttf` (OFL-1.1) + its
  `OFL.txt` license, downloaded from `google/fonts` (`ofl/pressstart2p/`).

## Milestones

1. **Map selector** — `MapViewer` + `MapMenu` (two-level folder/map
   browser), `list_map_folders` + `list_maps_in_folder` + `load_map`,
   error handling, low-res map rendering, rose-pine palette + pixel
   font. Shipped and headless-tested via `tests/conftest.py` dummy SDL
   drivers. [done]
2. **Pathfinding** — CBS low level: `dist_to_goal` (reverse Dijkstra)
   + `find_path_timed` (time-expanded A* with vertex/link constraints)
   in `src/simulation/pathfinding.py`. [done]
3. **Simulation GUI controls** — the `←`/`→` step keys wired to
   `Simulation.step()` / snapshot rewind (engine landed:
   `src/simulation/engine.py`). [done]
4. **Polish** — drone animation states, per-zone accents/status dots.