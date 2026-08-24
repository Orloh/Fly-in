# CLI Output Implementation Plan

## Summary
Implement the text-based simulation output for `make run` and `make debug` (currently stubbed at `src/__main__.py:28`).

## Decisions (confirmed)
- **Format**: `D{drone_id}-{to_zone}` per movement, joined by single space, drone-id order.
- **Header**: Echo normalized map (`nb_drones`, zones, connections) before movement lines.
- **Empty turns**: Print blank line for turns with no movements (in-transit only).
- **Deadlock**: Break when a turn has no movements AND no drones `IN_TRANSIT`.
- **Conflicts**: Print to stderr only with `--debug`.
- **Colors**: ANSI truecolor (rose-pine palette), auto-disabled on non-tty or `NO_COLOR`.
- **Errors**: `ParseError`/`OSError` → `Error: {msg}` to stderr, exit 1.

## Files to create/modify

### 1. `src/cli.py` (new — mirrors `src/gui/app.py`)
Pure, testable CLI layer.

**Exports:**
- `PALETTE` — dict of role→(r,g,b) (gold, foam, rose, pine, text, muted)
- `paint(text: str, role: str, color: bool = False) -> str`
- `format_map(parsed: ParsedMap, color: bool = False) -> list[str]`
- `format_turn(result: TurnResult, color: bool = False) -> str`
- `simulate(graph: Graph, drones: list[Drone], color: bool = False) -> Iterator[str]`
- `run(map_path: str, debug: bool = False, color: bool | None = None) -> None`

### 2. `src/__main__.py`
Replace the stub:
```python
from src.cli import run
run(args.map, debug=args.debug)
```
Add `--no-color` flag for explicit control.

### 3. `tests/test_cli.py` (TDD — write first)
Reuse `_graph`/`_drone` helpers from `tests/test_engine.py`.

**Test coverage:**
- `format_turn` — exact plain string, colored prefix, empty line, id ordering.
- `format_map` — header structure, blank-line separator, metadata ordering.
- `simulate` — single drone, restricted-zone empty line, deadlock break, multi-drone simultaneous moves.

## Output example
```
nb_drones: 3
start_hub: base 0 0
end_hub: target 400 300 [color=green]
hub: roof1 200 -100
hub: corridorA 300 150 [color=blue zone=priority]
hub: vault 350 -150 [zone=restricted]
hub: landing 150 250 [color=red]
connection: base-roof1 [max_link_capacity=3]
connection: roof1-corridorA
connection: corridorA-target
connection: base-landing
connection: landing-target
connection: roof1-vault

D1-landing
D2-landing

D1-corridorA
...
```
(Blank line = empty turn; ANSI colors when tty)

## Verification
- `uv run pytest tests` (real signal — `make test` masks failures via `|| true`)
- `make lint` (mypy strict + flake8, 79 cols)
- `make run MAP=maps/example.map` / `make debug MAP=maps/island.map` to eyeball

## Architecture notes
- Mirrors GUI pattern: pure helpers in module, thin `run()` orchestrator.
- No pygame, no side effects in formatters — fully unit-testable.
- `--debug` gates conflict stderr output.
- Color detection: `sys.stdout.isatty() and not os.getenv("NO_COLOR")`.