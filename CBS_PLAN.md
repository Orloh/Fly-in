# CBS_PLAN.md — Optimal-turn fleet routing via Conflict-Based Search

## Summary

Replace greedy per-drone routing with a two-level solver that minimizes
the **makespan** (the turn the last drone arrives) — the objective stated
in `Summary.md`. High level: Conflict-Based Search (CBS) over a
constraint tree. Low level: time-expanded A* per drone, guided by a
reverse-Dijkstra heuristic. The engine keeps its turn loop and output
contract; it replays a `Schedule` computed once at `Simulation.__init__`.

## Problem

Current code optimizes per-drone shortest paths and retries blocked hops
reactively (`_ensure_path` / `_capacity_conflict` in
`src/simulation/engine.py`). Same-goal drones receive the same
deterministic route and serialize through capacity-1 zones/links instead
of splitting across parallel routes.

Measured baseline (current engine, all drones arrive):

```
uv run python - <<'EOF'
from src.parser.parser import parse_map
from src.parser.converter import build_graph
from src.simulation.engine import Simulation
for name in ("bottleneck", "parallel_paths", "example",
             "complex_cycle", "simple_line", "priority_blocked"):
    graph, drones = build_graph(parse_map(f"maps/{name}.map"))
    sim = Simulation(graph, drones)
    while not sim.finished:
        sim.step()
    print(name, sim.state.turn)
EOF
```

| Map | Drones | Turns (current) | Turns (optimal) | Role |
|---|---|---|---|---|
| `bottleneck.map` | 8 | 19 | 11 | **gap map** — both chokes must be used |
| `example.map` | 3 | 5 | 4 | **gap map** — split landing/roof1 routes |
| `parallel_paths.map` | 6 | 9 | 9 | regression — merge-target binds at 1/turn |
| `priority_blocked.map` | 4 | 8 | 8 | regression — merge-target binds |
| `complex_cycle.map` | 5 | 9 | 9 | regression — e-target binds |
| `simple_line.map` | 4 | 7 | 7 | regression — chain, no alternatives |

Correction from earlier discussion: `parallel_paths.map` was assumed to
be the gap demo. Measured + computed analysis shows its `merge` zone and
`merge-target` link (both capacity 1) bound throughput to 1 drone/turn,
so greedy already matches optimal (9). The real gap maps are
`bottleneck.map` (19 → 11) and `example.map` (5 → 4).

## Verified movement contract

Ground truth pinned by `tests/test_engine.py`; the planner must
reproduce all of it:

- Earliest single-drone arrival = `1 + Σ entry costs` along the route
  (S→A→G all-normal = turn 3; S→R→G with R restricted = turn 4).
- A hop X→Y started at turn `t` with cost `c`: the drone is IN_TRANSIT
  (occupies **no** zone) during turns `t..t+c-1`, arrives at turn `t+c`,
  and may start the next hop that same turn.
- The link is held for the whole transit (a restricted hop holds it 2
  turns) and its `max_link_capacity` budget is shared across **both
  directions** (a head-on swap consumes 2).
- Zone capacity = concurrent occupants; start/end hubs unlimited.
- Waiting in place is free; a waiting drone occupies its zone.
- The start hub is unlimited → any drone can always wait at start → a
  planner with wait actions is **complete** for this domain.

## Architecture: augment, not rewrite

Preserved unchanged (verified by grep — no `find_path` / `drone.path`
usage outside `src/simulation/` and tests): the parser (`src/parser/`),
`Zone`/`Connection`/`Graph`, `TurnResult`/`Movement`, `src/cli.py`, and
all of `src/gui/` (the controller snapshots `Drone` objects, which keeps
working with new fields).

```
Graph (spatial)                      have — reused as-is
dist_to_goal (reverse Dijkstra)      new  — heuristic table, one per goal
find_path_timed (time-expanded A*)   new  — low level; find_path deleted
Planner (CBS high level)             new  — src/simulation/planner.py
Schedule / ScheduledAction           new  — src/models/schedule.py
Simulation.step (cursor replay)      refactored — reactive loop removed
TurnResult / Movement / CLI / GUI    unchanged external contract
```

Offline by design: the schedule is computed once at init and replayed
deterministically. No online re-planning — the spec has no mid-sim
dynamics, and makespan is fixed by the plan.

## Design decisions and tradeoffs

**D1 — CBS, not prioritized planning (PP).**
PP plans drones sequentially against earlier drones' reservations:
~100 lines, fast, but suboptimal (ordering-dependent splits) and the
whole point of this project is the fewest-turns optimum. Accepted cost:
CBS is ~250-400 lines and exponential in the worst case. At this map
scale (≤ 8 zones-visible routes, ≤ 8 drones) that is irrelevant.
Rejected "phased PP-first": the end state is known and the transitional
value was thin.

**D2 — Makespan objective; high-level best-first by makespan.**
Node cost = max arrival turn across drones. The classic CBS optimality
proof targets sum-of-costs; the makespan-ordered variant is used here
and is verified by the test-matrix bounds below. A violated bound is a
bug, not a design ceiling.

**D3 — Offline: plan once, replay.**
`Planner` runs in `Simulation.__init__`; `step()` is a cursor. Simplest
correct model for a static map; deterministic replays for the GUI
rewind (snapshot history unaffected — schedule is immutable data).

**D4 — Planned waits are silent.**
When the schedule holds a drone back (zone/link full), no conflict
string is emitted. Conflicts remain only for: (a) no route → drone
`BLOCKED` + "no route" (preserves `test_unreachable_goal_blocks_drone`),
and (b) safety-net violations (planner bugs). Accepted cost: ~4 conflict
assertions in `tests/test_engine.py` change (enumerated below). This
matches `Summary.md`'s "avoid conflicts" spirit: a good plan has none.

**D5 — One low level: `find_path_timed`; `find_path` is deleted.**
The CBS root needs timed routes anyway (conflict detection operates on
`(zone, turn)` / link intervals), so a static `list[str]` route would
need a converter — more code, not less. With no constraints and the
consistent heuristic, a wait strictly increases `f`, so the unconstrained
search never waits: the root degenerates to the forward Dijkstra and
returns the route already timed. The priority-zone tie-break
(`input_format.md`: priority zones "should be prioritized") moves into
the A* heap ordering. `find_path` has no remaining caller once the
engine switches (not the heuristic, not the GUI, not the CLI).

**D6 — Heuristic: `dist_to_goal`, one reverse Dijkstra per goal.**
`d(v, goal)` = cheapest remaining travel time ignoring other drones,
computed by reverse Dijkstra from the goal with edge weight
`u→v = enter_cost(v)` (1 / 2 / ∞). Then `f((v,t)) = t + d(v,goal)` —
the estimated arrival turn. Admissible and consistent: `d(v) ≤
enter(w) + d(w)` (min-definition), a hop raises `t` by exactly
`enter(w)` and lowers `d` by at most `enter(w)`; a wait raises `t` by 1.
All drones in real maps share the end hub (`converter.py` builds them
that way) → **one table serves every low-level search in the run**.
Constraints never affect `h` (a relaxation is always admissible); they
prune successors.

**D7 — Capacity conflicts, not binary.**
A conflict exists when the (N+1)th drone wants the same `(zone, turn)`
beyond `max_drones`, or overlaps on a link beyond `max_link_capacity`.
Branching picks two offenders and forbids one per child — correct for
capacities > 1 (at least one of any two offenders must leave the cell),
at the cost of a wider tree. Most shipped maps are cap-1.

**D8 — Post-arrival occupancy.**
An arrived drone occupies its goal for all future turns. Free for real
maps (end hub = unlimited), but required for correctness on
heterogeneous-goal scenarios (`test_head_on_collision...`: goals are
plain cap-1 zones).

**D9 — Time horizon `T`.**
Wait actions make the state space infinite; cap `t ≤ T` with
`T = 1 + n_drones × (Σ all zone entry costs)` — generous, never a tuning
knob. A low-level failure within `T` prunes that CBS child; a root
failure with no constraints means the goal is spatially unreachable.

**D10 — Bidirectional link budget preserved.**
Both directions share `max_link_capacity` (engine test
`test_head_on_collision_respect_link_capacity` pins this). The
conflict detector counts link occupancy under the canonical key.

**D11 — Planner injection.**
`Simulation(graph, drones, planner=None)` defaults to `Planner(graph)`
but accepts a stub/alternative — keeps the planner unit-testable and
the engine decoupled, matching the repo's controller style.

**D12 — Pydantic for artifacts, plain structures for search.**
`ScheduledAction`/`Schedule` are domain models (`src/models/schedule.py`,
pydantic, exported). The CBS occupancy index and constraint sets are
search internals in `planner.py` — plain dicts/tuples, no validation
overhead in hot loops.

## Alternatives considered (why CBS)

Optimal general solvers — the real competitors:

| Algorithm | Verdict for this project |
|---|---|
| Joint-space A* | `\|V\|^k × T` state space — dead at k = 8 drones. Operator Decomposition improves constants, not the exponent. |
| ICTS | Cost-tuple enumeration + MDD intersection; CBS-sized code, typically slower than CBS. |
| M* (subdimensional expansion) | Optimal and efficient when conflicts are rare, but collision-set/wildcard bookkeeping is the most complex of the family. |
| SAT / ILP / ASP | Requires an external solver — prohibited by the no-external-libs constraint. |

**Time-expanded max-flow (quickest flow)** — the one polynomial
alternative. Real maps give every drone the same
`(start_hub → end_hub)` (`converter.py`), so they are a
single-commodity evacuation problem: time-expanded network with
zone-capacity arcs, hold arcs for waits, and shared per-turn
link-occupancy arcs (both directions through the same budget arc);
binary-search the smallest `T` where max-flow = `nb_drones`;
decompose unit flows into timed routes. Provably makespan-optimal
for the homogeneous case, ~150 hand-written Dinic lines. Rejected:
heterogeneous goals (the engine tests, e.g. head-on) are
multi-commodity flow — NP-hard in general — so a second general
solver would still be needed. Two solvers for one job is worse
than one.

Bounded-suboptimal / scaling upgrades (not needed at ≤ 8 drones):

- **ECBS / w-CBS** — focal search, ≤ w× optimal; same architecture
  as CBS, so the code investment carries over. The named evolution
  if maps grow (see Risks).
- **LNS (MAPF-LNS2)** — PP init + destroy-and-repair of conflicting
  groups; near-optimal at 1000+ agents. At this scale CBS is exact
  and already fast.

Fast suboptimal:

- **Prioritized Planning** (D1) — ~100 lines, and it would likely
  find 11 on `bottleneck.map` anyway (drone 2's A* sees choke1
  reserved, so choke2 becomes its earliest arrival — it splits
  naturally). Rejected because it is ordering-dependent (lucky on
  one map, suboptimal on another) and incomplete when a drone parks
  forever on a finite-capacity goal another drone must cross —
  impossible on real maps (end hub unlimited) but exactly what the
  heterogeneous engine tests exercise. ~90% of the win for 25% of
  the code; the objective here is the optimum.
- **WHCA\*** (windowed cooperative A*) — rolling-horizon
  reservations + online replanning. The pre-CBS engine is a
  degenerate WHCA* (window 1, no reservations, retry-same-hop);
  this plan is a deliberate exit from that paradigm.

Rule-based online steppers:

- **PIBT** — per-turn priority inheritance + backtracking; huge
  fleets, near-optimal throughput on dense grids. Standard PIBT
  assumes unit vertex capacities, single-step moves, no
  swap-through; cap-N zones, 2-turn transits, and shared
  bidirectional link budgets are research-extension territory.
  Online stepping also discards the schedule/cursor architecture
  and GUI-rewind determinism.
- **Push&Swap / Rotate** — complete only on classical graphs
  (unit caps, 1-step moves); assumptions broken by this domain.

**Why CBS wins here:** it is the cheapest optimal *general* solver
(nothing else optimal is both tractable at k = 8 and implementable
without external libs); the domain extensions (cap-N, 2-turn
transits, bidirectional budgets, post-arrival occupancy) live in
one function — the conflict detector; it is complete where PP is
not (heterogeneous goals); and it preserves the plan-once →
schedule → cursor architecture. Worst-case exponentiality is
irrelevant at this scale.

## CBS design

### Data model

- `TimedRoute = list[tuple[str, int]]` — `(zone, arrival_turn)` pairs
  from `(start, start_turn)` to `(goal, arrival)`. A wait is a repeated
  zone with a later turn; consecutive pairs map 1:1 onto actions.
- `ScheduledAction` — `kind: WAIT|MOVE`, `turn`, `from_zone`, `to_zone`,
  `turns_required`. `Schedule` — per-drone dense action list covering
  every turn from 1 to arrival (dense = self-documenting replay).
- Constraints (per drone, CBS): `VertexConstraint(zone, turn)` — never
  occupy that zone at that turn (prune state `(zone, turn)`).
  `LinkConstraint(link, turn)` — never be on that link during that turn
  (prune moves whose transit interval `t..t+c-1` contains the turn).
- Occupancy index (high level only): `zone_time[(z,t)] -> count` and
  `link_time[(canon_link,t)] -> count`, built from all routes plus
  post-arrival tails. **In CBS the low level never sees other drones'**
  **paths** — the index exists purely to detect conflicts. (Reservations
  guiding the low level is the PP design; we are not doing that.)

### Low level: `find_path_timed`

```
find_path_timed(graph, start, goal, constraints, start_turn, horizon,
                dist) -> TimedRoute | None
```

- State `(zone, turn)`; start `(start, start_turn)`; goal = any
  `(goal, t)`; first popped goal state is the earliest feasible arrival.
- Successors from `(z, t)`:
  - wait → `(z, t+1)`: allowed if `t+1 ≤ horizon`, no vertex constraint
    on `(z, t+1)`, and zone capacity at `(z, t+1)`… capacity is enforced
    at the high level; the low level enforces only **constraints**.
  - move → `(w, t+c)` for each neighbor `w` (not blocked,
    `c = enter_cost(w)`): allowed if `t+c ≤ horizon`, no vertex
    constraint on `(w, t+c)`, and no link constraint on
    `(canonical(z,w), τ)` for any `τ in t..t+c-1`.
- Heap entry `(f, -priority_count, turn, zone)` with
  `f = t + d(zone, goal)`; deterministic; prefers priority zones on
  equal `f` (D5). `g` is not tracked separately — time is the cost.

### High level: `Planner`

1. Build `dist` tables — one per distinct goal.
2. Root: `find_path_timed` per distinct `(start, goal)` with no
   constraints; replicate per drone (real maps: one call). A drone whose
   root route is `None` is spatially unreachable → mark `BLOCKED` +
   "no route", exclude it from CBS.
3. Open list: heap by `(makespan, Σ arrivals, n_constraints)` —
   deterministic tie-breaks.
4. Pop a node → build the occupancy index → find the first conflict
   (minimum turn, then canonical cell name for determinism):
   - zone: `zone_time[(z,t)] > capacity(z)` (hubs skipped)
   - link: `link_time[(l,t)] > max_link_capacity(l)`
5. Conflict-free → **done**: convert routes to a `Schedule`; this node's
   makespan is optimal (D2).
6. Else pick two offenders (lowest drone ids), branch two children —
   each adds one constraint (vertex or link) for one offender at the
   conflicting `(cell, turn)` — and replan **only** that drone. A replan
   returning `None` prunes the child.
7. Expansion cap (50_000 nodes): degrade to the root schedule (greedy)
   and let the engine safety net surface violations as conflicts.
   Should never trigger at this scale.

### Engine integration

- `Simulation.__init__(graph, drones, planner=None)`:
  `schedule, blocked = planner.plan(drones)`; blocked drones get
  `BLOCKED` status up front.
- `step()`: arrivals first (unchanged countdown), then for each WAITING
  drone in id order, look up the action for the current turn:
  `MOVE` → `_start_hop` (reused, taking the action's `to_zone`/`turns`),
  `WAIT`/none → silently stay. The reactive `while True` loop,
  `_ensure_path`, `_zone_reservations`, and the `departing` computation
  are removed.
- Safety net: before committing a `MOVE`, run the capacity check; a
  violation appends a conflict (planner bug — visible via `--debug`)
  and degrades that drone to a wait.
- `Drone`: `schedule: list[ScheduledAction]` + `schedule_index: int`
  replace the mutable `path`; `turns_in_transit` tightens to `int`.
- CLI deadlock guard stays as belt-and-braces (cannot trigger on a valid
  schedule). GUI untouched (verified: no `drone.path` reads in `src/gui`).

## Files to create/modify

1. **`src/models/schedule.py`** (new) — `ScheduledAction`, `Schedule`;
   exported from `src/models/__init__.py`.
2. **`src/simulation/pathfinding.py`** (rewrite) — `dist_to_goal`,
   `find_path_timed`, keep `_enter_cost`; delete `find_path`/`Route`.
3. **`src/simulation/planner.py`** (new) — `Planner` (CBS), constraints,
   occupancy index, horizon computation, `TimedRoute` conversion.
4. **`src/models/drone.py`** (modify) — `schedule` + `schedule_index`
   replace `path`; `turns_in_transit: int`.
5. **`src/simulation/engine.py`** (rewrite `step`) — cursor replay,
   planner injection, safety net, no-route handling.
6. **`src/simulation/__init__.py`** (modify) — export `find_path_timed`,
   `dist_to_goal`, `TimedRoute` instead of `find_path`/`Route`.
7. **`src/parser/converter.py`** (no change) — `Drone` defaults cover
   the new fields.
8. **`tests/test_pathfinding.py`** (port) — the 10 properties
   re-expressed against `find_path_timed` (zone sequence + arrival
   turns): direct line, both endpoints, avoid restricted when cheaper,
   use restricted when only route, detour blocked, `None` unreachable,
   `None` blocked goal, prefer priority on ties, shortest beats longer
   priority route, start == goal.
9. **`tests/test_planner.py`** (new) — makespan bounds (matrix below),
   conflict-free schedules, unreachable handling, determinism.
10. **`tests/test_engine.py`** (modify) — 4 conflict assertions +
    new replay/safety-net tests (enumerated below).
11. **`tests/test_converter.py`** (modify) — `drone.path == []` →
    `drone.schedule == []` (line 387).
12. **`AGENTS.md`** (phase 5) — algorithm section: planned → implemented.
13. **`GUI_PLAN.md`** (phase 5, two lines) — the historical `find_path`
    mentions (shipped-milestones paragraph ~line 17, milestone 2
    ~line 124) get a one-line forward pointer to `find_path_timed` /
    `CBS_PLAN.md`. They are true today and only go stale when Phase 2
    deletes the symbol — so they are NOT touched before then.

## Phased execution (TDD — red first, per repo workflow)

- **Phase 1 — red tests.** Write `tests/test_planner.py` (matrix below),
  port `tests/test_pathfinding.py`, update `tests/test_engine.py` +
  `tests/test_converter.py`. Run `uv run pytest tests` — everything new
  fails (`find_path_timed` does not exist yet). Pin the exact optimal
  makespans for the regression maps while writing these.
- **Phase 2 — low level.** Implement `dist_to_goal` +
  `find_path_timed` in `pathfinding.py`; delete `find_path`.
  `test_pathfinding` goes green.
- **Phase 3 — planner.** Implement `planner.py` (CBS).
  `test_planner` goes green.
- **Phase 4 — engine.** `Drone` model change + `engine.py` cursor
  replay + injection. `test_engine` + `test_converter` go green; full
  suite green.
- **Phase 5 — verify + document.** `make lint` (mypy strict + flake8,
  79 cols, docstrings ≤ 4 lines), `uv run pytest tests`, manual runs
  (`make run MAP=maps/bottleneck.map` — expect 11 turns), update
  `AGENTS.md`, and touch up the two now-stale `find_path` mentions in
  `GUI_PLAN.md` (files list, item 13). `CLI_OUTPUT_PLAN.md`,
  `Summary.md`, and `input_format.md` need nothing — verified: zero
  references to any symbol CBS touches.

## Test matrix

Planner/engine makespan assertions (optimal values argued from the
movement contract; each lower bound is the binding-capacity argument):

| Scenario | Greedy | Optimal | Bound argument |
|---|---|---|---|
| `bottleneck.map` | 19 | **11** | each choke admits 1 entry / 2 turns (cap-1 link, 2-turn hold) → last entry ≥ T7 → arrival ≥ T7+4 |
| `example.map` | 5 | **4** | landing route serializes 1/turn (first T3); roof1 route earliest T4 → ≥ 2 drones arrive ≥ T4 |
| synthetic split: S→A→G ∥ S→B→G, all cap 1, 2 drones | 4 | **3** | single-drone makespan is 3; disjoint routes let both arrive T3 |
| single drone S→A→G (normal) | 3 | **3** | `1 + Σ costs` (existing test) |
| single drone S→R→G (restricted) | 4 | **4** | `1 + (2+1)` (existing test) |
| head-on A↔B, link cap 1 | 3 | **3** | one traverses T1, other waits, traverses T2, arrives T3 |
| `parallel_paths.map` | 9 | **9** | merge-target 1/turn from T4 → arrivals T4..T9 |
| `priority_blocked.map` | 8 | **8** | merge-target binds |
| `complex_cycle.map` | 9 | **9** | e-target binds |
| `simple_line.map` | 7 | **7** | chain, no alternatives |

`tests/test_engine.py` changes (D4 — silent planned waits; movement and
turn-count assertions all stay):

- `test_zone_capacity_makes_second_drone_wait` →
  `first.conflicts == []` (drone 2 still WAITING at S).
- `test_link_capacity_makes_second_drone_wait` →
  `first.conflicts == []`.
- `test_restricted_link_is_not_reused_while_held` → conflicts `[]`
  on both asserted turns (link_usage counts stay).
- `test_head_on_collision_respect_link_capacity` →
  `first.conflicts == []` (1 movement, makespan 3).
- Keep unchanged: `test_unreachable_goal_blocks_drone` ("no route"
  conflict preserved), `test_drones_processed_in_id_order`, all
  turn-count assertions (3, 4, 4), single-drone tests, empty fleet.
- Add: schedule replay in id order; safety-net fires on an injected
  bad schedule → conflict + wait (planner-bug channel).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| CBS blow-up on adversarial maps | horizon `T` + expansion cap with greedy-root degradation; upgrade path (CG/DG heuristics, ECBSD) noted, out of scope |
| Makespan-CBS optimality subtlety (D2) | test-matrix bounds are proofs-by-construction; a violation is a bug |
| Cap > 1 widens the conflict tree | two-offender branching stays correct; shipped maps are mostly cap-1 |
| Planner/executor model drift | safety-net check + visible conflict string; identical `Movement` records |
| Horizon too small prunes valid children | generous formula (D9); CBS returning `None` with spatial routes present is a flagged bug, not silent failure |
| Test churn (4 assertions + 10 ported) | behaviors preserved, only re-expressed; enumerated above |

## Verification

```
make lint                       # mypy strict + flake8, must be clean
uv run pytest tests             # real signal (make test masks failures)
make run MAP=maps/bottleneck.map    # expect 11 turns (was 19)
make run MAP=maps/example.map       # expect 4 turns (was 5)
make run MAP=maps/parallel_paths.map  # expect 9 (unchanged — regression)
make debug MAP=maps/bottleneck.map  # conflicts absent (silent waits)
make gui MAP=maps/bottleneck.map    # replay + rewind still work
```
