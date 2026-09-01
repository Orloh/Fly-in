# AGENTS.md — Fly-in

Drone fleet routing simulation. Python 3.10+, Pydantic models, `uv` package manager.

## Commands

```
make install      # uv sync --group dev
make run MAP=maps/example.map   # uv run python -m src <map>
make gui MAP=maps/example.map   # uv run python -m src --gui <map>
make debug MAP=maps/example.map # uv run python -X dev -m src --debug <map>
make lint         # uv run mypy src tests && uv run flake8 src
make clean        # nuke .venv, .mypy_cache
make test         # uv run pytest tests || true   ← swallows failures
```

### Gotchas

- **`make test` masks failures** (`|| true` in the Makefile). For a real
  pass/fail signal run `uv run pytest tests` directly.
- **`make run`/`make debug`** run the text-based simulation (stdout:
  map header + per-turn `D{id}-{zone}` lines). Colors auto-disable on
  non-tty or `NO_COLOR`. Conflicts only shown with `--debug`.
- **Single test:** `uv run pytest tests/test_engine.py::Class::test_name`
  or `uv run pytest tests/test_pathfinding.py -k pattern`.
- **Required order:** edit → `make lint` (mypy + flake8) →
  `uv run pytest tests` (never `make test`).

## Architecture

- **Entry point:** `src/__main__.py` — invoked as `python -m src <map>`.
  Dispatches `--gui` → `src/gui/app.py`, else → `src/cli.py`.
- **`pyproject.toml`** has `package = false` — application, not a library.
- **Domain models** in `src/models/`, all `pydantic.BaseModel`. Parsing
  is two-stage: `src/models/parsing.py` holds raw-file models
  (`ParsedMap`, `ParsedZone`, `ParsedConnection`) that convert into
  `Zone`/`Connection`/`Graph` via `build_graph`.
- **`Graph`** wraps `dict[str, Zone]` + `dict[tuple[str,str], Connection]`
  with a `cached_property` adjacency index. Connections are undirected —
  key is always `(a, b)` with `a <= b`; use `canonical_key` in
  `src/models/graph_utils.py`.
- **Start/end hubs** have unlimited capacity: `Zone.capacity` returns
  `None` for hubs, `max_drones` otherwise.
- **Absolute imports** everywhere, including tests (`from src.*`).

## Algorithm & objective gap (fix planned: CBS)

`Summary.md` states the primary goal: *"all drones reach their
destination in the fewest possible simulation turns"* (makespan). The
current code does NOT achieve it — `find_path` is per-drone Dijkstra
and the engine block-and-retries conflicts, so same-goal drones queue
on one route instead of splitting. **Decision made: implement
optimal-makespan Conflict-Based Search (CBS). Read `CBS_PLAN.md` before
touching `src/simulation/`** — it holds the full design, tradeoffs,
measured baselines, test matrix, and phased TDD plan.

Locked decisions (do not re-litigate):
- Planner/executor split: `Planner` computes a `Schedule` once in
  `Simulation.__init__`; `step()` replays it as a cursor. Offline only —
  no online re-planning.
- `find_path` is deleted → `find_path_timed` (time-expanded A*) +
  `dist_to_goal` (reverse-Dijkstra heuristic) in `pathfinding.py`. The
  priority-zone tie-break moves into the A* heap ordering.
- Planned waits are silent — no conflict string when the schedule holds
  a drone back. Conflicts remain only for no-route (`BLOCKED`) and
  safety-net planner violations.
- Conflict model is capacity-based (N+1th drone at a `(zone, turn)` or
  link interval); link budgets are shared across both directions;
  arrived drones keep occupying finite-capacity goals.
- Measured baseline: `bottleneck.map` 19 → optimal 11 and
  `example.map` 5 → 4 are the gap maps. `parallel_paths.map` 9 = 9,
  `priority_blocked.map` 8 = 8, `complex_cycle.map` 9 = 9 are
  merge/exit-bound regression maps, NOT gap maps.

Until implementation lands, this section describes planned state, not
current state. When it lands, rewrite this section as implemented and
document the new entry points (`planner.py`, `find_path_timed`,
`src/models/schedule.py`).

## Constraints

- **No external graph libraries** — no `networkx`, no `graphlib`. All
  pathfinding hand-written.
- **Line length:** 79 chars (flake8 in pyproject.toml).
- **mypy strict mode** — `strict = true`, `check_untyped_defs = true`.
- **Zone names** cannot contain `-` or spaces (validated in `Zone`).
- All models use `from __future__ import annotations`.

## Workflow

- **Before committing:** show the commit message and wait for explicit
  approval before running `git commit`.
- **Docstrings:** every class, method, and function must have one. 4
  lines max — state what, not how.
- **Test-driven:** write tests in `tests/` before implementing; run
  `uv run pytest tests` (not `make test`).
- **After any code change:** run `make lint` and fix all issues before
  declaring work done.

## Map format

Defined in `input_format.md`. Key rules:
- First line: `nb_drones: <int>`. Exactly one `start_hub:` and one
  `end_hub:`.
- Zones: `start_hub`/`end_hub`/`hub: <name> <x> <y> [metadata]`. Hubs
  have infinite capacity.
- Connections: `connection: <zoneA>-<zoneB> [metadata]`, strictly
  bidirectional; duplicates (`a-b` after `b-a`) are invalid.
- Zone types: `normal` (cost 1), `priority` (cost 1, preferred),
  `restricted` (cost 2), `blocked` (inaccessible). Invalid type →
  parse error.
- Metadata (any order in `[...]`): `zone=`, `color=`,
  `max_drones=` (default 1), `max_link_capacity=` (default 1).
- Any parse failure halts with line number and cause.

## CLI Output

- **Module:** `src/cli.py` — pure, testable layer mirroring
  `src/gui/app.py`.
- **Exports:** `format_map`, `format_turn`, `simulate`, `run`, plus
  `PALETTE`/`paint` for ANSI truecolor.
- **Format:** per-turn line `D{id}-{to_zone} ...` (drone-id order); map
  header echoed first (normalized from `ParsedMap`); blank line for
  turns with no movements (in-transit only).
- **Zone-name coloring:** a zone's `color=` metadata maps to a rose-pine
  role (red→rose, blue→iris, green→pine, cyan→foam, gold→gold, plus
  synonyms). The zone NAME token is painted in the map header and in
  `D{id}-{to_zone}` lines.
- **Termination:** deadlock guard — break when a turn yields no
  movements AND no drone is `IN_TRANSIT`. Final arrival turn with no
  movements is not printed.
- **Colors:** rose-pine truecolor, auto-disabled when stdout is not a
  TTY or `NO_COLOR` is set.
- **Conflicts:** stderr only with `--debug`. **Errors:**
  `ParseError`/`OSError` → `Error: {msg}` to stderr, exit 1.
- **Tests:** `tests/test_cli.py` — pure formatter tests + `simulate`
  integration tests with **own fixtures** (it does **not** share
  `_graph`/`_drone` from `tests/test_engine.py`).

## Shared Palette

- **Module:** `src/palette.py` — pure, no pygame. Single source of truth
  for both CLI (ANSI) and GUI (RGB).
- **Exports:** `PALETTE` (role→RGB), `COLOR_NAME_TO_ROLE`,
  `color_role(color_name) -> str | None`. Both CLI and GUI import from
  here; no cross-layer coupling.

## GUI

- **Stack:** `pygame-ce` only — keyboard-driven, no widget library.
  Drawn on a low-res canvas (`VIRTUAL = (640, 360)`) in the pixel font
  **Press Start 2P** (OFL-1.1, vendored under `assets/fonts/`),
  upscaled with `pygame.transform.scale` (crisp pixels). Full design
  outline in `GUI_PLAN.md`.
- **Palette:** rose-pine (constants in `src/gui/constants.py` and
  `src/palette.py`).
- **Controls:** `SPACE` play/pause, `BACKSPACE` rewind, `+`/`-` speed
  (wraps), `M` map picker (↑/↓ move, ENTER load, ESC/M close), `ESC`
  quit. Displayed `SPEEDS` = 0.5/1/2/4×; actual `SPEED_RATES` are half,
  for watchability.
- **Layering:** `src/gui/` is decoupled from the engine — pure helpers
  (`transform.layout`, `maps.list_maps`, `menu.MapMenu`,
  `controller.SimController`) plus the pygame/app drawing code
  (`app.py`). `MapViewer` delegates sim control to `self.controller`.
- **Shared constants:** `src/gui/constants.py` holds `SPEEDS`,
  `SPEED_RATES`, `TOAST_DURATION_MS` to avoid circular imports between
  `app.py` and `controller.py`.
- **Headless GUI tests:** `tests/conftest.py` sets
  `SDL_VIDEODRIVER`/`SDL_AUDIODRIVER = dummy` before pygame init.
  pytest must run from project root (the font path is CWD-relative).
- Keep the map folder named `maps/` (scanned by the picker).

## Deferred decisions

- **Self-loop connections (`connection: A-A`)**: undecided. The parser
  accepts them and the converter does not reject them; `input_format.md`
  is silent. If disallowed, add a check (and test) in
  `_convert_connection`.

## Known gaps

- **No `README.md`** at root, though `Summary.md` lists it as a required
  deliverable (project description, running instructions, resources, AI
  utilization, algorithm explanation). Needs to be written.