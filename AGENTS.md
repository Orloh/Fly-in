# AGENTS.md — Fly-in

Drone fleet routing simulation. Python 3.10+, Pydantic models, `uv` package manager.

## Commands

```
make install      # uv sync --group dev
make run MAP=maps/example.map   # uv run python -m src <map>
make debug MAP=maps/example.map # uv run python -X dev -m src --debug <map>
make lint         # mypy src && flake8 src
make clean        # nuke .venv, __pycache__, .mypy_cache
```

## Architecture

- **Entry point:** `src/__main__.py` — invoked as `python -m src <map_file>`.
- **`pyproject.toml`** has `package = false` — this is an application, not a distributable library.
- **Domain models** live in `src/models/`, all subclass `pydantic.BaseModel`.
- **Parsing is two-stage:** `src/models/parsing.py` holds raw-file models (`ParsedMap`, `ParsedZone`, `ParsedConnection`). These convert into domain models (`Zone`, `Connection`, `Graph`) in a separate step.
- **`Graph`** wraps `dict[str, Zone]` + `dict[tuple[str,str], Connection]` with a `cached_property` adjacency index.
- **Connections are undirected** — key is always `(a, b)` with `a <= b` (lexicographic sort).
- **Start/end hubs** have unlimited capacity: `Zone.capacity` returns `None` for hubs, `max_drones` otherwise.

## Constraints

- **No external graph libraries** — no `networkx`, no `graphlib`. All pathfinding must be hand-written.
- **Line length:** 79 chars (flake8 config in pyproject.toml).
- **mypy strict mode** — `strict = true`, `check_untyped_defs = true`.
- **Zone names** cannot contain `-` or spaces (validated in `Zone` model).
- All models use `from __future__ import annotations` for deferred evaluation.

## Workflow

- **Before committing:** always show the commit message and wait for explicit approval before running `git commit`.
- **Docstrings:** every class, method, and function must have a docstring. 4 lines max — state what it does, not how.
- **After lint:** run `make lint` after any code change and fix all issues before declaring work done.

## Map format

Defined in `input_format.md`. Key rules:
- First line: `nb_drones: <int>`
- Exactly one `start_hub:` and one `end_hub:`
- Connections: `connection: <zoneA>-<zoneB> [metadata]`
- Zone types: `normal` (cost 1), `priority` (cost 1), `restricted` (cost 2), `blocked` (inaccessible)
- Error on any parse failure — halt with line number and cause.
