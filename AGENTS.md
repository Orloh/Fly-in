# AGENTS.md — Fly-in

Drone fleet routing simulation. Python 3.10+, Pydantic models, `uv` package manager.

## Commands

```
make install      # uv sync --group dev
make run MAP=maps/example.map   # uv run python -m src <map>
make gui MAP=maps/example.map   # uv run python -m src --gui <map>
make debug MAP=maps/example.map # uv run python -X dev -m src --debug <map>
make lint         # mypy src && flake8 src
make clean        # nuke .venv, __pycache__, .mypy_cache
make test         # uv run pytest tests || true   ← swallows failures
```

### Gotchas

- **`make test` masks failures** (`|| true` in the Makefile). For a real
  pass/fail signal run `uv run pytest tests` directly.
- **`make run`/`make debug` exit with "simulation run not implemented
  yet"** — the CLI simulation path is a stub. Use `make gui` to see a
  rendered map instead.

## Architecture

- **Entry point:** `src/__main__.py` — invoked as `python -m src <map_file>`.
- **`pyproject.toml`** has `package = false` — this is an application, not a distributable library.
- **Domain models** live in `src/models/`, all subclass `pydantic.BaseModel`.
- **Parsing is two-stage:** `src/models/parsing.py` holds raw-file models (`ParsedMap`, `ParsedZone`, `ParsedConnection`). These convert into domain models (`Zone`, `Connection`, `Graph`) in a separate step.
- **`Graph`** wraps `dict[str, Zone]` + `dict[tuple[str,str], Connection]` with a `cached_property` adjacency index.
- **Connections are undirected** — key is always `(a, b)` with `a <= b` (lexicographic sort).
- **Start/end hubs** have unlimited capacity: `Zone.capacity` returns `None` for hubs, `max_drones` otherwise.
- **Absolute imports** everywhere, including tests: `from src.*`. No relative imports.
- **Build status:** parser, converter, and the GUI map selector are
  fully implemented and tested (`parse_map` + helpers, `build_graph`
  + `_convert_zone` + `_convert_connection`, `src/gui/` with pure
  helpers `transform.layout` + `maps.list_maps`/`load_map`, and the
  `MapViewer` window with a working map dropdown). Pathfinding,
  simulation engine, and drone movement are not built yet.

## Deferred decisions

- **Self-loop connections (`connection: A-A`)**: not yet decided. The
  parser currently accepts them and the converter does not reject them.
  Left open until real `maps/*.map` files clarify whether self-loops are
  allowed; if disallowed, add a check (and test) in `_convert_connection`.

## Constraints

- **No external graph libraries** — no `networkx`, no `graphlib`. All pathfinding must be hand-written.
- **Line length:** 79 chars (flake8 config in pyproject.toml).
- **mypy strict mode** — `strict = true`, `check_untyped_defs = true`.
- **Zone names** cannot contain `-` or spaces (validated in `Zone` model).
- All models use `from __future__ import annotations` for deferred evaluation.

## Workflow

- **Before committing:** always show the commit message and wait for explicit approval before running `git commit`.
- **Docstrings:** every class, method, and function must have a docstring. 4 lines max — state what it does, not how.
- **Test-driven:** write tests in `tests/` before implementing; run them with `uv run pytest tests` (see gotcha above — `make test` hides failures).
- **After lint:** run `make lint` after any code change and fix all issues before declaring work done.

## GUI

- **Stack:** `pygame-ce` (rendering; drop-in for the `pygame` module)
  + `pygame-gui` (widgets, added with `uv add pygame-gui`). Widgets
  come from pygame-gui — no hand-rolled buttons/dropdowns/sliders.
  Detailed outline in `GUI_PLAN.md`.
- **Rendering style:** retro pixel-art. The map is drawn to a low-res
  canvas (`VIRTUAL = (640, 360)`) and upscaled to the window
  (`1280 × 720`, `SCALE = 2`) with `pygame.transform.scale`
  (nearest-neighbor = crisp pixels). pygame-gui is drawn at **native
  window resolution** — its text upscales fuzzily, so the UI stays
  crisp while the map stays chunky (Minecraft-style).
- **Theme:** rose-pine palette in `assets/theme.json` — bg `#191724`,
  gold `#f6c177`, rose `#eb6f92`, foam `#9ccfd8`, iris `#c4a7e7`,
  pine `#31748f`, text `#e0def4`. Pixel font **Press Start 2P**
  (OFL-1.1, vendored under `assets/fonts/` with its license).
- **Theme gotchas:** pygame-gui resolves a font `regular_path` against
  the **process working directory** (not the theme file), so run
  `make gui`/pytest from the project root; `drop_down_menu.misc
  .expand_direction: "up"` is a theme option, not a constructor arg;
  `drop_down_menu.#expand_button` is left on the default
  `fira_code_symbols` because Press Start 2P lacks the ▾ glyph.
- **GUI layer lives in `src/gui/`**, decoupled from the simulation
  engine: pure helpers (`transform.layout`, `maps.list_maps`) plus the
  pygame/app drawing code (`app.py`).
- **Map selector:** `UIDropDownMenu` bottom-left
  (`expand_direction="up"`), options from `list_maps(maps_dir)`.
  Selection reloads the map via `load_map`; parse/IO failures show a
  5-second bottom-center toast (boxed, rose-bordered) and keep the
  current map. An empty `maps/` yields no dropdown and a persistent
  "no maps found" toast. Widgets are built in `MapViewer._build_ui` so
  future controls slot in additively.
- **Headless GUI tests:** `tests/conftest.py` sets `SDL_VIDEODRIVER` /
  `SDL_AUDIODRIVER = dummy` before pygame initializes, so `MapViewer`
  smoke tests (`tests/test_gui_app.py`) run without a display. The
  theme font `regular_path` resolves against the CWD, so pytest must
  run from the project root.
- **Resizable window:** the window opens with `pygame.RESIZABLE` and
  the map stretches to fill any size. `VIDEORESIZE`/`WINDOWSIZECHANGED`
  events are handled by `MapViewer._on_window_resized`, which re-applies
  `set_mode`, syncs `manager.set_window_resolution`, and re-anchors the
  dropdown to the bottom-left.
- **Planned controls** (pygame-gui, not built yet): play/pause
  `UIButton`, step-back `UIButton`, velocity `UIHorizontalSlider`.
  Widgets are built in a central factory so these slot in additively.
- Keep the map folder named `maps/` (scanned by the dropdown).

## Map format

Defined in `input_format.md`. Key rules:
- First line: `nb_drones: <int>`
- Exactly one `start_hub:` and one `end_hub:`
- Connections: `connection: <zoneA>-<zoneB> [metadata]`
- Zone types: `normal` (cost 1), `priority` (cost 1), `restricted` (cost 2), `blocked` (inaccessible)
- Error on any parse failure — halt with line number and cause.
