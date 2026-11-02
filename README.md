*This project has been created as part of the 42 curriculum by orhernan.*

# Fly-in — Drone Fleet Routing Simulation

## Description

A turn-based simulation that routes a fleet of drones from a start hub to
an end hub across a network of zones and connections, minimizing the
**makespan** — the number of turns until the last drone arrives. Written
in Python 3.10, fully type-checked with mypy (strict) and flake8-clean.

Routing uses a deterministic **greedy prioritized planner**: drones are
planned in id order, and each route respects the capacity reservations
of all previously committed routes. Output is a Google-colored
truecolor terminal interface.

### Features

- Capacity-aware greedy fleet routing with per-turn zone and link
  reservations.
- Simultaneous movement with strict capacity rules per zone and link.
- Zone types: `normal` (1), `priority` (1, preferred), `restricted` (2),
  `blocked` (inaccessible).
- Full map parser with line-numbered error messages.
- CLI: Google-colored truecolor terminal output (`D1-zoneA D2-zoneB` per turn).
- Deterministic replays and reproducible benchmark results.

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
make debug MAP=maps/personal/bottleneck.txt   # pdb debugger + conflict tracing
make stats MAP=maps/easy/01_linear_path.txt   # CLI + stats block
make run-all                                  # all tier maps with --stats
```

#### Command line

```
python -m src <map> [--debug] [--no-color] [--stats] [--map]
```

| Arg | Meaning |
|-----|---------|
| `map` (positional) | path to the map file |
| `--debug` | print engine conflicts to stderr |
| `--no-color` | disable ANSI truecolor (default: auto, off on non-TTY / `NO_COLOR`) |
| `--stats` | append a stats block after the turns: blank line, `== Stats ==`, secondary metrics and the makespan |
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

The CLI uses a Google-inspired truecolor palette:

- normal zones and the end hub use Google Blue,
- priority zones and the start hub use Google Green,
- restricted zones use Google Yellow,
- blocked zones use Google Gray,
- drone ids use Google Yellow,
- errors and conflicts use Google Red.

Zone names can also be colored by their `color=` metadata. Unknown
single-word colors get a deterministic Google-palette fallback.

Colors are auto-disabled when stdout is not a TTY or when `NO_COLOR` is
set. The movement lines make waits, bottlenecks, and capacity pressure
easy to spot, while `--debug` prints engine conflicts to stderr.

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
  __main__.py        # entry point: python -m src <map> [--debug]
  parser/            # parse_map (raw file) -> converter.build_graph
  models/            # pydantic: Zone, Connection, Graph, Drone, Schedule, ...
  simulation/
    pathfinding.py   # dist_to_goal (reverse Dijkstra), find_path_timed (A*)
    planner.py       # Greedy prioritized planner with capacity reservations
    engine.py        # Simulation: replays the Schedule turn by turn
  cli.py             # terminal output layer
  palette.py         # Google truecolor palette
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
it as a cursor. Each `TurnResult` also carries the projected end-of-turn
`zone_occupancy`, `moved_zones`, and per-zone `capacities` for
diagnostics or future output extensions. Planned waits are silent; conflicts are limited
to no-route drones and safety-net planner bugs (visible with `--debug`).

### Benchmark checks

Run `make benchmark` to run the tier benchmark suite. Makespans are
produced by the greedy prioritized planner for every supplied map.

## Resources

- Python 3.10, [pydantic](https://docs.pydantic.dev/), `uv`.
- Google brand colors for terminal output.
- Timed A* and greedy prioritized planning.

### AI utilization

This project was developed iteratively with an AI coding assistant
(opencode). Concretely, AI was used for:

- Implementing the two-stage map parser (`src/parser/`) and its
  line-numbered error handling.
- Building the greedy prioritized planner (`src/simulation/planner.py`)
  as described in the Algorithm section.
- Designing the turn-based engine (`src/simulation/engine.py`) and its
  conflict-free schedule replay model.
- The Google-inspired terminal palette (`src/palette.py`).
- Writing the test suite and the tiered benchmark maps.

Human review covered the algorithm choices, reservation model, test
expectations, and final polish; every AI-generated component was read,
validated, and tested before adoption.