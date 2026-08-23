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
- **Build status:** parser, converter, GUI map selector, **pathfinding**, and
  the **simulation engine** are fully implemented and tested
  (`parse_map` + helpers, `build_graph` + `_convert_zone` +
  `_convert_connection`, `src/gui/` pure helpers `transform.layout` +
  `maps.list_maps`/`load_map`, `MapViewer` with keyboard-driven map
  picker; `find_path` + `_enter_cost` in `src/simulation/pathfinding.py`;
  `Simulation` with capacity/link/route-conflict handling in
  `src/simulation/engine.py` — 10 engine + 10 pathfinding tests passing).
  Drone movement is handled inside the engine (no separate module).

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

- **Stack:** `pygame-ce` only — all controls are keyboard-driven, no
  widget library. The map, key legend, map picker, and toast are all
  drawn to a low-res canvas (`VIRTUAL = (640, 360)`) in the pixel font
  and upscaled with `pygame.transform.scale` (nearest-neighbor = crisp
  pixels). Detailed outline in `GUI_PLAN.md`.
- **Palette:** rose-pine (code constants in `app.py`) — bg `#191724`,
  gold `#f6c177`, rose `#eb6f92`, foam `#9ccfd8`, iris `#c4a7e7`,
  pine `#31748f`, text `#e0def4`. Pixel font **Press Start 2P**
  (OFL-1.1, vendored under `assets/fonts/` with its license).
- **Keyboard controls:** the bottom-left legend (`_draw_legend`) shows
  the bindings. `SPACE` = play/pause (single-steps while paused),
  `BACKSPACE` = rewind one turn (snapshot history), `+`/`-` = set speed
  and start auto-play (`SPEEDS = 0.5/1/2/4×` turns/sec, wraps, shown
  live), `M` = toggle the map picker. In the picker: `UP`/`DOWN` move,
  `ENTER` loads, `ESC`/`M` close. `ESC` quits when the picker is closed.
- **Map picker:** hand-drawn centered overlay (`_draw_menu`) on top of
  the `MapMenu` state machine in `src/gui/menu.py` (pure, tested in
  `tests/test_gui_menu.py`). Options from `list_maps(maps_dir)`,
  refreshed on open, current map pre-highlighted. Parse/IO failures
  show a 5-second top-center toast (boxed, rose-bordered) and keep
  the current map; an empty `maps/` yields a persistent "no maps found"
  toast and no picker.
- **GUI layer lives in `src/gui/`**, decoupled from the simulation
  engine: pure helpers (`transform.layout`, `maps.list_maps`,
  `menu.MapMenu`) plus the pygame/app drawing code (`app.py`).
- **Headless GUI tests:** `tests/conftest.py` sets `SDL_VIDEODRIVER` /
  `SDL_AUDIODRIVER = dummy` before pygame initializes, so `MapViewer`
  smoke tests (`tests/test_gui_app.py`) run without a display. pytest
  must run from the project root (the font path is CWD-relative).
- **Resizable window:** opens at `WINDOW = (1280, 720)` with
  `pygame.RESIZABLE`. On `VIDEORESIZE`/`WINDOWRESIZED`/
  `WINDOWSIZECHANGED`, `_on_resized` re-creates the window at the new
  size (pygame-ce reports the size in `x`/`y` for `WINDOWSIZECHANGED`);
  same-size events are ignored (loop guard). The canvas is stretched to
  fill the window, so nothing is re-laid-out on resize.
- Keep the map folder named `maps/` (scanned by the picker).

## Map format

Defined in `input_format.md`. Key rules:
- First line: `nb_drones: <int>`
- Exactly one `start_hub:` and one `end_hub:`
- Connections: `connection: <zoneA>-<zoneB> [metadata]`
- Zone types: `normal` (cost 1), `priority` (cost 1), `restricted` (cost 2), `blocked` (inaccessible)
- Error on any parse failure — halt with line number and cause.
