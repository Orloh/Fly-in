# CBS_PLAN.md — Optimal-turn fleet routing

## Summary

Replace greedy per-drone routing with a solver that minimizes the
**makespan** (the turn the last drone arrives) — the objective stated in
`Summary.md`. Two solvers, dispatched by fleet structure:

- **Homogeneous fleets** (every drone shares `(start_hub → end_hub)` —
  all real/shipped maps, per `converter.py`): **time-expanded max-flow
  (quickest flow)**. Single-commodity evacuation; polynomial and
  provably makespan-optimal.
- **Heterogeneous fleets** (multi-commodity — the head-on engine tests):
  **Conflict-Based Search (CBS)** over a constraint tree. Low level:
  time-expanded A* per drone, guided by a reverse-Dijkstra heuristic.

`Planner` is a dispatcher: it picks the flow solver for homogeneous
fleets and falls back to CBS for anything else. The engine keeps its
turn loop and output contract; it replays a `Schedule` computed once at
`Simulation.__init__`.

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
    graph, drones = build_graph(parse_map(f"maps/personal/{name}.txt"))
    sim = Simulation(graph, drones)
    while not sim.finished:
        sim.step()
    print(name, sim.state.turn)
EOF
```

| Map | Drones | Turns (current) | Turns (optimal) | Role |
|---|---|---|---|---|
| `bottleneck.txt` | 8 | 19 | 11 | **gap map** — both chokes must be used |
| `example.txt` | 3 | 5 | 4 | **gap map** — split landing/roof1 routes |
| `parallel_paths.txt` | 6 | 9 | 9 | regression — merge-target binds at 1/turn |
| `priority_blocked.txt` | 4 | 8 | 8 | regression — merge-target binds |
| `complex_cycle.txt` | 5 | 9 | 9 | regression — e-target binds |
| `simple_line.txt` | 4 | 7 | 7 | regression — chain, no alternatives |

Correction from earlier discussion: `parallel_paths.txt` was assumed to
be the gap demo. Measured + computed analysis shows its `merge` zone and
`merge-target` link (both capacity 1) bound throughput to 1 drone/turn,
so greedy already matches optimal (9). The real gap maps are
`bottleneck.txt` (19 → 11) and `example.txt` (5 → 4).

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

## Alternatives considered

Optimal general solvers — the real competitors:

| Algorithm | Verdict for this project |
|---|---|
| Joint-space A* | `\|V\|^k × T` state space — dead at k = 8 drones. Operator Decomposition improves constants, not the exponent. |
| ICTS | Cost-tuple enumeration + MDD intersection; CBS-sized code, typically slower than CBS. |
| M* (subdimensional expansion) | Optimal and efficient when conflicts are rare, but collision-set/wildcard bookkeeping is the most complex of the family. |
| SAT / ILP / ASP | Requires an external solver — prohibited by the no-external-libs constraint. |

**Time-expanded max-flow (quickest flow)** — ✅ ADOPTED as the primary
solver for homogeneous fleets. Real maps give every drone the same
`(start_hub → end_hub)` (`converter.py`), so they are a
single-commodity evacuation problem: time-expanded network with
zone-capacity arcs, hold arcs for waits, and shared per-turn
link-occupancy arcs (both directions through the same budget arc);
binary-search the smallest `T` where max-flow = `nb_drones`;
decompose unit flows into timed routes. Provably makespan-optimal
for the homogeneous case, ~150 hand-written Dinic lines.

It was originally rejected as the *sole* solver because heterogeneous
goals (the engine tests, e.g. head-on) are multi-commodity flow —
NP-hard in general — so a second solver would still be needed. That
argument still holds: the final architecture is **flow for homogeneous,
CBS for heterogeneous**, dispatched by `Planner`. See the dedicated
section below.

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

## Quickest-flow primary solver (homogeneous fleets)

Adopted after CBS shipped (Phase 5+). `Planner` dispatches: homogeneous
fleets → flow; heterogeneous → CBS. Full design in `src/simulation/flow.py`.

### Network model (time-expanded over turns 1..T)

- Zone nodes `(zone, turn)`, each split `in → out` with capacity
  `cap(zone)` (∞ for hubs) — enforces `max_drones` per turn.
- `Source → (start, 1)_in`, capacity `nb_drones`.
- Wait arcs `(z,t)_out → (z,t+1)_in` — the zone in/out split governs.
- Move arcs through a **link-capacity chain**: for neighbor `w` with
  `c = enter_cost(w)`, route
  `(z,t)_out → L[canon(z,w), t] → … → L[canon(z,w), t+c-1] → (w, t+c)_in`,
  each `L[link, τ]` capped at `max_link_capacity` — enforces the
  shared per-turn bidirectional link budget (incl. 2-turn restricted
  holds).
- **Post-arrival occupancy:** arrived drones ride goal wait-arcs to `T`
  then exit to sink, so finite-capacity goals are never exceeded across
  arrival turns (free for the unlimited end_hub).
- Blocked zones (∞ enter cost) are never move destinations.

### Solving

1. Unreachable drones marked `BLOCKED` via the existing `find_path_timed`
   root pre-pass.
2. **Binary search** the smallest `T` where `max_flow == n_drones`
   (upper bound = greedy makespan / horizon) → optimal makespan.
3. **Decompose** the max-flow into unit paths in deterministic source-
   edge order; truncate each at the first `(goal, t)` → `TimedRoute`.
4. Reuse `_route_to_actions` to build the `Schedule` (routes assigned to
   interchangeable drones by arrival order).
5. **Validate** the schedule with `_cost_consistent` — every MOVE's
   `turns_required` must equal the destination zone's entry cost. If the
   splice corrupted it, `Planner` falls back to CBS.

### Tradeoffs vs CBS

- **Flow:** polynomial, optimal for homogeneous fleets when the shared
  link chain is splice-free (all-normal maps), no exponential search.
- **Splice caveat (structural, not a bug).** The shared per-turn link
  chain lets a drone "splice" into another move's tail on restricted
  links, producing an invalid 1-turn transit into a restricted zone
  (e.g. bottleneck → 8 instead of 11). `Planner` therefore validates the
  flow schedule for cost-consistency (`_cost_consistent`: every MOVE's
  `turns_required` equals the destination zone's entry cost) and falls
  back to CBS when it fails. CBS is optimal, so the makespan is correct
  either way; flow is the primary solver only on maps where it is sound.

  Why the splice is not fixed in the network: the engine's link capacity
  is occupancy-based (a drone holds a restricted link for 2 turns, so at
  most `max_link_capacity` drones are in transit at a turn). Enforcing
  that per-turn sum requires a shared capacity node, but a shared node
  merges anonymous flow units and loses each unit's transit position, so
  its fan-out re-enables the early exit. Position-tagged nodes prevent
  the splice but cannot share a per-turn capacity sum; the direct-arc
  (rate) model allows two drones on a cap-1 two-turn link. Measured:
  shared chain, per-position, position+shared-sum, and direct-arc all
  give bottleneck = 8; CBS gives the correct 11. This is a known
  limitation of anonymous single-commodity flow, not a missing fix.
- **Flow cannot** handle multi-commodity (different goals) — the head-on
  engine tests — which is why CBS remains as the fallback. `Planner`
  checks `_is_homogeneous(drones)` and dispatches.
- Plain max-flow does not prefer priority zones (soft `input_format.md`
  tie-break); a min-cost extension could add it later. Makespan is
  unaffected.

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
2. **`src/simulation/pathfinding.py`** (rewrite) — ✅ DONE (Phase 2).
   `dist_to_goal` + `find_path_timed` implemented with `State`,
   `Constraints`, `TimedRoute`, `VertexConstraint`, `LinkConstraint`,
   `Heuristic` aliases; `_enter_cost` kept. `find_path`/`Route` were
   kept as legacy until Phase 4 and are now deleted.
3. **`src/simulation/planner.py`** (new) — ✅ DONE (Phase 3). `Planner`
   (CBS), constraints, occupancy index, horizon computation,
   `TimedRoute` conversion, agent-symmetry dedup, `_assign_routes`.
4. **`src/models/drone.py`** (modify) — ✅ DONE (Phase 4). `schedule`
   + `schedule_index` replace `path`; `turns_in_transit: int`;
   `blocked_reason: str | None` added.
5. **`src/simulation/engine.py`** (rewrite `step`) — ✅ DONE (Phase 4).
   `Simulation.__init__(graph, drones, planner=None)` runs the Planner
   once; `step()` is a cursor replay of `ScheduledAction`s; safety net
   checks the schedule's occupancy; blocked drones report "no route" on
   the first step.
6. **`src/simulation/__init__.py`** (modify) — ✅ DONE. Exports
   `find_path_timed`, `dist_to_goal`, `TimedRoute`,
   `VertexConstraint`, `LinkConstraint`, `Planner`, `sum_entry_cost`;
   `find_path`/`Route` removed (Phase 4).
7. **`src/parser/converter.py`** (no change) — `Drone` defaults cover
   the new fields.
8. **`tests/test_pathfinding.py`** (port) — ✅ DONE (Phase 1+2). 20
   tests green: 7 `dist_to_goal` + 11 `find_path_timed` + 2 constraint
   cases + horizon cutoff. Covers the 10 properties from the matrix.
9. **`tests/test_planner.py`** (new) — ✅ DONE (Phase 1+3). 15 tests
   green: makespan bounds (matrix below), conflict-free schedules,
   unreachable handling, determinism.
10. **`tests/test_engine.py`** (modify) — ✅ DONE (Phase 4). 4 conflict
    assertions flipped to silent planned waits; new schedule-replay and
    safety-net tests added.
11. **`tests/test_converter.py`** (modify) — ✅ DONE (Phase 4).
    `drone.path == []` → `drone.schedule == []`.
12. **`AGENTS.md`** (phase 5) — algorithm section: planned → implemented.
13. **`GUI_PLAN.md`** (phase 5, two lines) — the historical `find_path`
    mentions (shipped-milestones paragraph ~line 17, milestone 2
    ~line 124) get a one-line forward pointer to `find_path_timed` /
    `CBS_PLAN.md`. They are true today and only go stale when Phase 4
    deletes the symbol — so they are NOT touched before then.
14. **`src/simulation/flow.py`** (new, phase 6) — ✅ DONE. `Dinic`
    max-flow, time-expanded network builder, `FlowPlanner`
    (`PlannerProtocol`).
15. **`src/simulation/planner.py`** (modify, phase 6) — ✅ DONE.
    Dispatch: homogeneous → `FlowPlanner` (schedule cost-validated via
    `_cost_consistent`), else CBS, else greedy (>8 drones / cap hit).
16. **`src/simulation/__init__.py`** (modify, phase 6) — ✅ DONE.
    Exports `FlowPlanner`.
17. **`tests/test_flow.py`** (new, phase 6) — ✅ DONE. 12 tests: Dinic
    unit tests, decomposition, homogeneous map makespans, determinism,
    cost-consistency, heterogeneous fallback.

## Phased execution (TDD — red first, per repo workflow)

- **Phase 1 — red tests.** ✅ DONE. `tests/test_planner.py` (matrix
  below), `tests/test_pathfinding.py` ported (20 tests). `test_engine` +
  `test_converter` updates done in Phase 4. Phase 1 verified: new tests
  failed before implementation landed.
- **Phase 2 — low level.** ✅ DONE. `dist_to_goal` (reverse Dijkstra)
  and `find_path_timed` (time-expanded A*) implemented in
  `pathfinding.py`; all 20 `test_pathfinding` tests green. `find_path`
  was kept as legacy until Phase 4 and is now deleted. Low-level
  signature finalized: `find_path_timed` takes a single
  `constraints: Constraints` tuple
  `(set[VertexConstraint], set[LinkConstraint])`. `find_path_timed`
  returns a `TimedRoute` (`list[(zone, arrival_turn)]`) or `None`.
- **Phase 3 — planner.** ✅ DONE. `planner.py` implements the CBS high
  level: per-goal `dist_to_goal` cache, horizon
  `1 + n_drones × sum_entry_cost`, occupancy index with post-arrival
  tails, first-conflict detection, two-offender branching, and
  agent-symmetry dedup keyed by sorted route multiset (kills the
  exponential blowup on homogeneous fleets). `_assign_routes` maps
  routes to interchangeable drones deterministically by arrival order.
  `test_planner` green (15 tests).
- **Phase 4 — engine.** ✅ DONE. `Drone` model now holds
  `schedule: list[ScheduledAction]` + `schedule_index`; `turns_in_transit`
  is `int`. `engine.py` runs the `Planner` once in `__init__` and `step()`
  replays actions as a cursor (WAIT/MOVE lookups in id order). Planned
  waits are silent; conflicts are only no-route (BLOCKED drones, first
  step) and safety-net violations (schedule's own occupancy model, for
  planner bugs). `find_path`/`Route` deleted from `pathfinding.py` and
  `src/simulation/__init__.py`. `test_engine` + `test_converter` green.
- **Phase 5 — verify + document.** ✅ DONE. `make lint` clean, full
  suite green, `AGENTS.md` rewritten, `GUI_PLAN.md` stale `find_path`
  mentions touched up. Valid greedy fallback added for >8 drone fleets
  (hard/challenger maps), fixing the cap-degradation deadlock.
- **Phase 6 — quickest-flow primary.** ✅ DONE. `src/simulation/flow.py`
  implements `Dinic` + the time-expanded network + `FlowPlanner`; `Planner`
  dispatches homogeneous → flow, heterogeneous → CBS. The shared link
  chain can splice a 1-turn transit into a restricted zone, so the flow
  schedule is cost-validated (`_cost_consistent`) and used only when
  sound, otherwise CBS runs (CBS is optimal, so the makespan is correct
  either way). `tests/test_flow.py` added (12 tests); full suite green
  (242 tests), `make lint` clean, all map makespans verified. See the
  "Quickest-flow primary solver" section above for the splice caveat and
  the three-way dispatch.

## Test matrix

Planner/engine makespan assertions (optimal values argued from the
movement contract; each lower bound is the binding-capacity argument):

| Scenario | Greedy | Optimal | Bound argument |
|---|---|---|---|
| `bottleneck.txt` | 19 | **11** | each choke admits 1 entry / 2 turns (cap-1 link, 2-turn hold) → last entry ≥ T7 → arrival ≥ T7+4 |
| `example.txt` | 5 | **4** | landing route serializes 1/turn (first T3); roof1 route earliest T4 → ≥ 2 drones arrive ≥ T4 |
| synthetic split: S→A→G ∥ S→B→G, all cap 1, 2 drones | 4 | **3** | single-drone makespan is 3; disjoint routes let both arrive T3 |
| single drone S→A→G (normal) | 3 | **3** | `1 + Σ costs` (existing test) |
| single drone S→R→G (restricted) | 4 | **4** | `1 + (2+1)` (existing test) |
| head-on A↔B, link cap 1 | 3 | **3** | one traverses T1, other waits, traverses T2, arrives T3 |
| `parallel_paths.txt` | 9 | **9** | merge-target 1/turn from T4 → arrivals T4..T9 |
| `priority_blocked.txt` | 8 | **8** | merge-target binds |
| `complex_cycle.txt` | 9 | **9** | e-target binds |
| `simple_line.txt` | 7 | **7** | chain, no alternatives |

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
make run MAP=maps/personal/bottleneck.txt    # expect 11 turns (was 19)
make run MAP=maps/personal/example.txt       # expect 4 turns (was 5)
make run MAP=maps/personal/parallel_paths.txt  # expect 9 (unchanged — regression)
make debug MAP=maps/personal/bottleneck.txt  # conflicts absent (silent waits)
make gui MAP=maps/personal/bottleneck.txt    # replay + rewind still work
```
