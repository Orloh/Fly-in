# GUI_PLAN.md — Retro pixel-art GUI for Fly-in

A roadmap for the graphical layer of Fly-in: the visual style, the
keyboard-driven controls, and the technologies behind it. Supersedes
the earlier "add a simple pygame window" idea — the GUI is now a
first-class landing pad for the future simulation controls.

## Main idea

One window that renders the current map as chunky retro pixel-art with
all controls on the keyboard — no mouse widgets. The map, the key
legend, the map picker, and the toast are all drawn to a low-res canvas
and upscaled, so the whole frame reads as one cohesive arcade look in a
single rose-pine palette and one pixel font.

Shipped milestones: the **map picker** (keyboard-driven), **pathfinding**
(`find_path` + `_enter_cost` in `src/simulation/pathfinding.py`, 10 tests),
and the **simulation engine** (`Simulation` in `src/simulation/engine.py`,
10 tests: turn stepping, capacity/link conflicts, head-on swaps). The step
forward/back and speed-cycle keys are wired as stubs ready to drive the
engine.

## Libraries and technologies

| Piece | Choice | Why |
|---|---|---|
| Rendering | `pygame-ce` (drop-in for `pygame`) | Frame-based animation, simple draw primitives |
| Fonts | Bundled TTF | **Press Start 2P** (SIL OFL-1.1), vendored under `assets/fonts/` with the license |
| Palette | Rose-pine as code constants in `app.py` | bg/gold/rose/foam/pine/text — no theme file needed |
| Layout math | Pure helpers in `src/gui/` (`transform.layout`, `maps.list_maps`, `menu.MapMenu`) | Testable without pygame |

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
- **UI on the same canvas:** the legend, the picker, and the toast are
  drawn on the low-res canvas too, so they inherit the chunky look and
  scale with the map on resize (no native-res layer).
- **Font:** Press Start 2P for UI text and map labels; small sizes
  (≈8–10px) on the low-res map canvas.
- **Overlays:** flat, blocky boxes (thin borders, no shadows) so the UI
  matches the chunky map instead of fighting it.

## Controls (all keyboard)

| Key | Scope | Behaviour |
|---|---|---|
| `SPACE` | global | Step the simulation forward (stub — engine landed, wire to `Simulation.step()`) |
| `BACKSPACE` | global | Step the simulation back (stub) |
| `+` / `-` | global | Cycle simulation speed through `0.5×, 1×, 2×, 4×` (wraps; shown live in the legend) |
| `M` | global | Toggle the map picker (options refreshed on open) |
| `↑` / `↓` | picker | Move the highlighted map |
| `ENTER` | picker | Load the highlighted map, closing the picker |
| `ESC` | picker / global | Close the picker; quit when the picker is closed |

The bottom-left **legend** (`_draw_legend`) lists the bindings and the
live speed. The **map picker** (`_draw_menu`) is a centered overlay on
the `MapMenu` state machine; parse/IO failures show a 5s top-center
toast (boxed, rose-bordered) and keep the current map (persistent toast
when `maps/` is empty).

## Layout / architecture

```
src/gui/
  app.py        # MapViewer class: window, key routing, drawing, loop
  maps.py       # pure: list_maps() + load_map() (parse/convert/layout)
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
   (`SPACE`, `BACKSPACE`, `+`/`-`, `M`) apply.
2. Draw the map onto the 640 × 360 canvas (rose-pine palette, pixel
   font), then the toast, the legend, and the picker overlay.
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

1. **Map selector** — `MapViewer` + `MapMenu`, `list_maps` + `load_map`,
   error handling, low-res map rendering, rose-pine palette + pixel
   font. Shipped and headless-tested via `tests/conftest.py` dummy SDL
   drivers. [done]
2. **Pathfinding** — Dijkstra-based `find_path` with priority-zone
   tie-breaks, restricted/blocked zone costs, 10 tests passing.
   [`src/simulation/pathfinding.py`] [done]
3. **Simulation GUI controls** — the `SPACE`/`BACKSPACE` step keys and
   the `+`/`-` speed cycle wired to `Simulation.step()` (engine landed:
   `src/simulation/engine.py`).
4. **Polish** — drone animation states, per-zone accents/status dots.