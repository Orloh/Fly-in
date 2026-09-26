# Fly-in — Drone Fleet Routing Simulation

A turn-based simulation that routes a fleet of drones from a start hub to
an end hub across a network of zones and connections, minimizing the
**makespan** — the turn the last drone arrives. Written in Python 3.10,
fully type-checked with mypy (strict) and flake8-clean.

Routing uses **Conflict-Based Search (CBS)** for provably optimal-makespan
plans, replayed deterministically by the engine. Both a color terminal
output and a retro pixel-art GUI (pygame-ce) are included.

## Features

- Optimal fleet routing via CBS (capacity-aware zone and link conflicts).
- Simultaneous movement with strict capacity rules per zone and link.
- Zone types: `normal` (1), `priority` (1, preferred), `restricted` (2),
  `blocked` (inaccessible).
- Full map parser with line-numbered error messages.
- CLI: rose-pine truecolor terminal output (`D1-zoneA D2-zoneB` per turn).
- GUI: keyboard-driven pixel-art viewer with play/pause, rewind, speed,
  and a map picker (Press Start 2P font, headless-testable).
- Deterministic replays — the GUI rewind restores exact turn snapshots.

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (package manager)

## Installation

```
make install
```

## Usage

```
make run MAP=maps/easy/01_linear_path.txt     # CLI simulation
make gui MAP=maps/easy/01_linear_path.txt     # pixel-art GUI
make debug MAP=maps/personal/bottleneck.txt   # CLI + conflict tracing
```

Maps ship in tiers under `maps/` (`easy/`, `medium/`, `hard/`,
`challenger/`) plus regression maps in `maps/personal/`. The map format
is documented in `input_format.md`.

### GUI controls

| Key | Action |
|-----|--------|
| `SPACE` | play/pause (single-step while paused) |
| `BACKSPACE` | rewind one turn |
| `+` / `-` | cycle speed (0.5×, 1×, 2×, 4×) |
| `M` | map picker (↑/↓ move, ENTER load, ESC/M close) |
| `ESC` | quit |

## Development

```
make lint        # mypy strict + flake8
uv run pytest tests   # real pass/fail signal (make test masks failures)
```

Test-driven: write tests in `tests/` first, then `make lint` and
`uv run pytest tests`. The design and measured baselines live in
`CBS_PLAN.md` and `GUI_PLAN.md`.

## Architecture

```
src/
  __main__.py        # entry point: python -m src <map> [--gui] [--debug]
  parser/            # parse_map (raw file) -> converter.build_graph
  models/            # pydantic: Zone, Connection, Graph, Drone, Schedule, ...
  simulation/
    pathfinding.py   # dist_to_goal (reverse Dijkstra), find_path_timed (A*)
    planner.py       # Planner: optimal-makespan Conflict-Based Search
    engine.py        # Simulation: replays the Schedule turn by turn
  cli.py             # terminal output layer
  palette.py         # shared rose-pine palette (CLI + GUI)
  gui/               # pygame-ce viewer (app, controller, menu, transform)
```

## Algorithm

The objective is the **makespan**: the fewest turns until every drone
reaches the end hub. Two drones conflict when a zone's `max_drones` or a
link's `max_link_capacity` would be exceeded at a given turn (links share
their budget across both directions; arrived drones keep occupying
finite-capacity goals).

**Conflict-Based Search (CBS)** is a two-level solver:

1. **Low level — time-expanded A\*** (`find_path_timed`). Searches the
   `(zone, turn)` state space for one drone, guided by a consistent
   reverse-Dijkstra heuristic (`dist_to_goal`, the cost to reach the goal
   ignoring other drones). A `constraints` pair
   (`set[VertexConstraint]`, `set[LinkConstraint]`) prunes forbidden
   `(zone, turn)` occupancies and link transits. Equal-cost paths prefer
   priority zones.
2. **High level — constraint tree** (`Planner`). Each node holds one
   route per drone. Its routes are merged into an occupancy index; the
   first conflict (lowest turn) splits the node into two children, each
   adding one constraint to one of the two offending drones and
   re-planning only that drone. The first conflict-free node is
   makespan-optimal. A route-multiset dedup key kills the exponential
   blowup on homogeneous fleets (all drones share the start/end hub).

The plan is computed **once** at `Simulation.__init__` and `step()`
replays it as a cursor — planned waits are silent; the only conflicts are
no-route drones (blocked) and safety-net planner bugs (visible with
`--debug`).

### Measured results

| Map | Before (greedy) | After (CBS) |
|-----|-----------------|-------------|
| `maps/personal/bottleneck.txt` | 19 | **11** |
| `maps/personal/example.txt` | 5 | **4** |
| `maps/personal/parallel_paths.txt` | 9 | 9 (optimal) |
| `maps/personal/priority_blocked.txt` | 8 | 8 (optimal) |
| `maps/personal/complex_cycle.txt` | 9 | 9 (optimal) |
| `maps/personal/simple_line.txt` | 7 | 7 (optimal) |

## Resources

- Python 3.10, [pydantic](https://docs.pydantic.dev/), `uv`.
- GUI: [pygame-ce](https://pyga.me/) + vendored **Press Start 2P**
  font (SIL OFL-1.1, `assets/fonts/OFL.txt`).
- Rose-pine color palette.
- CBS literature: Sharon et al., "Conflict-Based Search for Optimal
  Multi-Agent Pathfinding" (2015).

## AI utilization

This project was developed iteratively with an AI coding assistant
(opencode). The assistant contributed the implementation, tests, and
refactors described above, following the design documents in the
repository (`CBS_PLAN.md`, `GUI_PLAN.md`). Human review covered the
algorithm choices, test expectations, and final polish.