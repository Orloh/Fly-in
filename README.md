*This project has been created as part of the 42 curriculum by orhernan.*

# Fly-in — Drone Fleet Routing Simulation

A turn-based simulation that routes a fleet of drones from a start hub to
an end hub across a network of zones and connections, minimizing the
**makespan** — the turn the last drone arrives. Written in Python 3.10,
fully type-checked with mypy (strict) and flake8-clean.

Routing produces provably optimal-makespan plans, replayed
deterministically by the engine. Homogeneous fleets (every drone
start_hub → end_hub) use a **time-expanded max-flow (quickest flow)**
solver; multi-commodity fleets fall back to **Conflict-Based Search
(CBS)**. Both a color terminal output and a retro pixel-art GUI
(pygame-ce) are included.

## Features

- Optimal fleet routing via quickest flow (homogeneous) / CBS
  (heterogeneous) — capacity-aware zone and link conflicts.
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
make debug MAP=maps/personal/bottleneck.txt   # pdb debugger + conflict tracing
make stats MAP=maps/easy/01_linear_path.txt   # CLI + stats block
make run-all                                  # all tier maps with --stats
```

### Command line

```
python -m src <map> [--gui] [--debug] [--no-color] [--stats] [--map]
```

| Arg | Meaning |
|-----|---------|
| `map` (positional) | path to the map file |
| `--gui` | render the map in a pygame window instead of the text CLI |
| `--debug` | print engine conflicts to stderr |
| `--no-color` | disable ANSI truecolor (default: auto, off on non-TTY / `NO_COLOR`) |
| `--stats` | append a stats block after the turns: blank line, `==Stats==`, secondary metrics and the makespan |
| `--map` | echo the normalized map header before the turns (hidden by default) |

Maps ship in tiers under `maps/` (`easy/`, `medium/`, `hard/`,
`challenger/`) plus regression maps in `maps/personal/`. The map format
is documented in `input_format.md`.

## Example

Input (`maps/easy/01_linear_path.txt`):

```
nb_drones: 2
start_hub: start 0 0 [color=green]
hub: waypoint1 1 0 [color=blue]
hub: waypoint2 2 0 [color=blue]
end_hub: goal 3 0 [color=red]
connection: start-waypoint1
connection: waypoint1-waypoint2
connection: waypoint2-goal
```

Expected output (`make run MAP=maps/easy/01_linear_path.txt`):
stdout carries only the movement lines (subject VII.5); add `--map` to
echo the normalized map header first.

```
D1-waypoint1
D1-waypoint2 D2-waypoint1
D1-goal D2-waypoint2
D2-goal
```

With `--map --stats` the same run prepends the header and appends a
stats block (blank line, `==Stats==` header, secondary metrics, and the
makespan):

```
nb_drones: 2
start_hub: start 0 0 [color=green]
end_hub: goal 3 0 [color=red]
hub: waypoint1 1 0 [color=blue]
hub: waypoint2 2 0 [color=blue]
connection: start-waypoint1
connection: waypoint1-waypoint2
connection: waypoint2-goal

D1-waypoint1
D1-waypoint2 D2-waypoint1
D1-goal D2-waypoint2
D2-goal

==Stats==
moves_per_turn: 1.20
avg_turns_per_drone: 4.50
total_path_cost: 6
makespan: 5
```

Restricted zones take 2 turns. A drone mid-transit is reported as
`D<id>-<from>-<to>` (the connection name) until it lands, so a single
drone through a restricted tunnel yields:

```
D1-tunnel
D1-start-tunnel
D1-goal
```

### GUI controls

| Key | Action |
|-----|--------|
| `SPACE` | play/pause (single-step while paused) |
| `BACKSPACE` | rewind one turn |
| `+` / `-` | cycle speed (0.5×, 1×, 2×, 4×) |
| `M` | map picker (↑/↓ move, ENTER load, ESC/M close) |
| `ESC` | quit |

## Visual representation

Two complementary views of the same simulation:

- **CLI (rose-pine truecolor).** Zone names are painted according to
  their `color=` metadata (red→rose, blue→iris, green→pine, cyan→foam,
  gold→gold), drone ids are gold, and map-header `connection:` lines
  pine. Colors make bottleneck zones and congestion visible at a glance
  and are auto-disabled off a TTY or under `NO_COLOR`.
- **GUI (pygame-ce).** A low-res pixel-art canvas (640×360, upscaled)
  in the Press Start 2P font. Zones are drawn as nodes, connections as
  edges, and each drone as a moving sprite; `D{id}-{zone}` hop lines
  appear in a per-turn log. Play/pause, rewind, and speed controls let
  you scrub through a run, so conflicts, waits, and capacity deadlocks
  can be replayed and analyzed frame by frame. The rewind restores
  exact turn snapshots, and a map picker (`M`) switches files without
  restarting.

Together they make the schedule legible: you can watch the fleet feed
through a bottleneck, pause at a wait, and rewind to understand *why*
a drone held — which the raw turn log alone does not convey.

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
    flow.py          # FlowPlanner: time-expanded max-flow (homogeneous fleets)
    planner.py       # Planner: dispatches flow / CBS; CBS constraint tree
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

**Two solvers, dispatched by `Planner` on fleet structure:**

**1. Quickest flow — homogeneous fleets** (`FlowPlanner`). Since every
real map gives all drones the same `(start_hub → end_hub)`, the fleet is
a single-commodity evacuation. A **time-expanded network** over turns
`1..T` models zone capacity (zone in/out arcs), link capacity (per-turn
link chains, shared across both directions), and post-arrival goal
occupancy. **Binary-searching** the smallest `T` where max-flow equals
the drone count yields the optimal makespan; unit flows are decomposed
into timed routes. Polynomial and provably optimal for this case.

The shared link chain can "splice" a 1-turn transit into a restricted
zone, so the flow schedule is **validated for cost-consistency** and
used only when sound; otherwise the planner falls back to CBS (optimal).

**2. Conflict-Based Search (CBS) — heterogeneous fleets** (`Planner`).
Multi-commodity fleets (different goals, e.g. the head-on swap) are
NP-hard as flow, so CBS handles them:

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
   blowup on homogeneous fleets.

The plan is computed **once** at `Simulation.__init__` and `step()`
replays it as a cursor — planned waits are silent; the only conflicts are
no-route drones (blocked) and safety-net planner bugs (visible with
`--debug`).

### Measured results

| Map | Before (greedy) | After (flow/CBS) |
|-----|-----------------|------------------|
| `maps/personal/bottleneck.txt` | 19 | **11** |
| `maps/personal/example.txt` | 5 | **4** |
| `maps/personal/parallel_paths.txt` | 9 | 9 (optimal) |
| `maps/personal/priority_blocked.txt` | 8 | 8 (optimal) |
| `maps/personal/complex_cycle.txt` | 9 | 9 (optimal) |
| `maps/personal/simple_line.txt` | 7 | 7 (optimal) |

Makespans are produced by quickest flow on all-normal maps, CBS on
restricted maps ≤ 8 drones, and the greedy fallback on flow-invalid
maps > 8 drones (ultimate_challenge, impossible_dream — heuristic).

## Resources

- Python 3.10, [pydantic](https://docs.pydantic.dev/), `uv`.
- GUI: [pygame-ce](https://pyga.me/) + vendored **Press Start 2P**
  font (SIL OFL-1.1, `assets/fonts/OFL.txt`).
- Rose-pine color palette.
- CBS literature: Sharon et al., "Conflict-Based Search for Optimal
  Multi-Agent Pathfinding" (2015).

## AI utilization

This project was developed iteratively with an AI coding assistant
(opencode). Concretely, AI was used for:

- Implementing the two-stage map parser (`src/parser/`) and its
  line-numbered error handling.
- Building the routing solvers — the time-expanded quickest-flow planner
  (`src/simulation/flow.py`) and the Conflict-Based Search planner
  (`src/simulation/planner.py`) — following the design in `CBS_PLAN.md`.
- Designing the turn-based engine (`src/simulation/engine.py`) and its
  conflict-free schedule replay model.
- The pygame-ce GUI (`src/gui/`) and the shared rose-pine palette
  (`src/palette.py`), per `GUI_PLAN.md`.
- Writing the test suite and the tiered benchmark maps.

Human review covered the algorithm choices, the solver dispatch cascade
(flow → CBS → greedy), test expectations, and final polish; every
AI-generated component was read, validated, and tested before adoption.