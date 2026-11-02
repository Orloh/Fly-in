*This project has been created as part of the 42 curriculum by orhernan.*

# Fly-in — Drone Fleet Routing Simulation

## Description

A turn-based simulation that routes a fleet of drones from a start hub to
an end hub across a network of zones and connections, minimizing the
**makespan** — the number of turns until the last drone arrives. Written
in Python 3.10, fully type-checked with mypy (strict) and flake8-clean.

Routing uses a deterministic **greedy prioritized planner**: drones are
planned in id order, and each route respects the capacity reservations
of all previously committed routes. Both a color terminal output and a
retro pixel-art GUI (pygame-ce) are included.

### Features

- Capacity-aware greedy fleet routing with per-turn zone and link
  reservations.
- Simultaneous movement with strict capacity rules per zone and link.
- Zone types: `normal` (1), `priority` (1, preferred), `restricted` (2),
  `blocked` (inaccessible).
- Full map parser with line-numbered error messages.
- CLI: rose-pine truecolor terminal output (`D1-zoneA D2-zoneB` per turn).
- GUI: keyboard-driven pixel-art viewer with `←`/`→` turn stepping and
  a map picker (Press Start 2P font, headless-testable).
- Deterministic replays — the GUI rewind restores exact turn snapshots.

## Instructions

### Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (package manager)

### Installation

```
make install
```

### Usage

```
make run MAP=maps/easy/01_linear_path.txt     # CLI simulation
make gui MAP=maps/easy/01_linear_path.txt     # pixel-art GUI
make debug MAP=maps/personal/bottleneck.txt   # pdb debugger + conflict tracing
make stats MAP=maps/easy/01_linear_path.txt   # CLI + stats block
make run-all                                  # all tier maps with --stats
```

#### Command line

```
python -m src <map> [--gui] [--debug] [--no-color] [--stats] [--map] [--capacity]
```

| Arg | Meaning |
|-----|---------|
| `map` (positional) | path to the map file |
| `--gui` | render the map in a pygame window instead of the text CLI |
| `--debug` | print engine conflicts to stderr |
| `--no-color` | disable ANSI truecolor (default: auto, off on non-TTY / `NO_COLOR`) |
| `--stats` | append a stats block after the turns: blank line, `== Stats ==`, secondary metrics and the makespan |
| `--map` | echo the normalized map header before the turns (hidden by default) |
| `--capacity` | show occupancy/max capacity for zones in each turn; connections stay unchanged |

Maps ship in tiers under `maps/` (`easy/`, `medium/`, `hard/`,
`challenger/`) plus regression maps in `maps/personal/`. The map format
is documented in `input_format.md`.

#### GUI controls

| Key | Action |
|-----|--------|
| `→` | step forward one turn |
| `←` | step back one turn |
| `T` | toggle zone-name labels |
| `M` | map picker (↑/↓ move, ENTER load, ESC/M close) |
| `ESC` / `Ctrl+C` | quit |

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

With `--map --stats` the same run prepends the normalized map header and
appends the secondary metrics:

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

== Stats ==
moves_per_turn: 1.50
avg_turns_per_drone: 3.50
total_path_cost: 6
makespan: 4
```

Restricted zones take 2 turns. The launch turn reports the connection,
the next turn reports the destination, and the following turn reports
the next movement:

```
D1-start-tunnel
D1-tunnel
D1-goal
```

## Visual representation

Two complementary views of the same simulation:

- **CLI (rose-pine truecolor).** Zone names are painted according to
  their `color=` metadata (red→rose, blue→iris, green→pine, cyan→foam,
  gold→gold; other names get a deterministic palette fallback), drone
  ids are gold, and map-header `connection:` lines pine. Colors make
  bottleneck zones and congestion visible at a glance and are
  auto-disabled off a TTY or under `NO_COLOR`.
- **GUI (pygame-ce).** A low-res pixel-art canvas (640×360, upscaled)
  in the Press Start 2P font. Zones are drawn as nodes, connections as
  edges, and each drone as a moving sprite; `D{id}-{zone}` hop lines
  appear in a per-turn log. The `←`/`→` step controls let you scrub
  through a run, so conflicts, waits, and capacity deadlocks can be
  replayed and analyzed frame by frame. The rewind restores exact turn
  snapshots, and a map picker (`M`) switches files without restarting.

Together they make the schedule legible: you can watch the fleet feed
through a bottleneck, pause at a wait, and rewind to understand *why*
a drone held — which the raw turn log alone does not convey.

## Development

```
make lint        # mypy strict + flake8
uv run pytest tests   # real pass/fail signal (make test masks failures)
```

Test-driven: write tests in `tests/` first, then `make lint` and
`uv run pytest tests`. Algorithm details are documented below; measured
baselines can be reproduced with `make benchmark`.

## Architecture

```
src/
  __main__.py        # entry point: python -m src <map> [--gui] [--debug]
  parser/            # parse_map (raw file) -> converter.build_graph
  models/            # pydantic: Zone, Connection, Graph, Drone, Schedule, ...
  simulation/
    pathfinding.py   # dist_to_goal (reverse Dijkstra), find_path_timed (A*)
    planner.py       # Greedy prioritized planner with capacity reservations
    engine.py        # Simulation: replays the Schedule turn by turn
  cli.py             # terminal output layer
  palette.py         # shared rose-pine palette (CLI + GUI)
  gui/               # pygame-ce viewer (app, controller, menu, transform)
```

## Algorithm

The objective is the **makespan**: the fewest turns until every drone
reaches the end hub. Two drones conflict when a zone's `max_drones` or a
link's `max_link_capacity` would be exceeded at a given turn.

**Greedy prioritized planning** (`Planner`). Drones are processed in
ascending id order:

1. Drone 1 is routed with time-expanded A* using no reservations.
2. Its route is committed.
3. The planner builds occupancy for committed routes and converts every
   cell that is already at capacity into a constraint:
   `(zone, turn)` for zones and `(link, turn)` for connections.
4. Drone 2 is routed with A* while respecting those constraints.
5. The process repeats for every drone.

The low-level search is `find_path_timed` (`src/simulation/pathfinding.py`):
it searches the `(zone, turn)` state space, uses a reverse-Dijkstra
heuristic from the goal, and permits waiting. Equal-cost paths prefer
priority zones. Restricted zones cost two turns and occupy their link
during transit.

Because each new drone is planned around already-full cells, the final
schedule is conflict-free by construction. The planner is fast and
deterministic, but not guaranteed to minimize makespan: early drone id
choices can force later drones to wait or detour.

The plan is computed **once** at `Simulation.__init__`; `step()` replays
it as a cursor. Planned waits are silent; conflicts are limited to
no-route drones and safety-net planner bugs (visible with `--debug`).

### Benchmark checks

Run `make benchmark` to run the tier benchmark suite. Makespans are
produced by the greedy prioritized planner for every supplied map.

## Resources

- Python 3.10, [pydantic](https://docs.pydantic.dev/), `uv`.
- GUI: [pygame-ce](https://pyga.me/) + vendored **Press Start 2P**
  font (SIL OFL-1.1, `assets/fonts/OFL.txt`).
- Rose-pine color palette.

### AI utilization

This project was developed iteratively with an AI coding assistant
(opencode). Concretely, AI was used for:

- Implementing the two-stage map parser (`src/parser/`) and its
  line-numbered error handling.
- Building the greedy prioritized planner (`src/simulation/planner.py`)
  as described in the Algorithm section.
- Designing the turn-based engine (`src/simulation/engine.py`) and its
  conflict-free schedule replay model.
- The pygame-ce GUI (`src/gui/`) and the shared rose-pine palette
  (`src/palette.py`), including its headless test suite.
- Writing the test suite and the tiered benchmark maps.

Human review covered the algorithm choices, reservation model, test
expectations, and final polish; every AI-generated component was read,
validated, and tested before adoption.