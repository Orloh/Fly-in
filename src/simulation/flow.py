"""Time-expanded max-flow (quickest flow) planner for homogeneous fleets.

All real maps give every drone the same ``(start_hub -> end_hub)``
(``converter.py``), so the fleet is a single-commodity evacuation: a
time-expanded network over turns ``1..T`` models zone capacity and
per-turn link budgets. Binary-searching the smallest ``T`` where
max-flow equals the drone count yields the optimal makespan; unit flows
decompose into timed routes.

The shared per-turn link chain is exact for cost-1 transits. Restricted
zones (cost 2) are modeled by chaining two link nodes per turn; the
network allows a drone to "splice" into another move's tail there, so
the resulting schedule is validated for cost-consistency by the caller,
which falls back to CBS when the flow schedule is invalid.
"""

from __future__ import annotations

import sys

from src.models import Drone, DroneStatus, Graph, canonical_key
from src.models.schedule import Schedule
from src.simulation.pathfinding import (
    _enter_cost,
    dist_to_goal,
    sum_entry_cost,
)
from src.simulation.planner import _route_to_actions

#: Sentinel for unlimited capacity (hubs, wait arcs).
_INF = 10**9

#: Dinic's DFS can chain hundreds of edges on large maps.
sys.setrecursionlimit(100_000)


class Dinic:
    """Hand-written Dinic max-flow (no external graph libraries)."""

    def __init__(self, n: int) -> None:
        """Allocate the residual adjacency list for ``n`` nodes."""
        self.graph: list[list[list[int]]] = [[] for _ in range(n)]
        self.forward: list[tuple[int, int, int, int]] = []

    def add_edge(self, u: int, v: int, cap: int) -> None:
        """Add a directed edge ``u -> v`` with capacity ``cap``."""
        self.graph[u].append([v, len(self.graph[v]), cap])
        self.graph[v].append([u, len(self.graph[u]) - 1, 0])
        self.forward.append((u, v, cap, len(self.graph[u]) - 1))

    def _bfs(self, s: int, t: int, level: list[int]) -> bool:
        """Build the level graph; return whether ``t`` is reachable."""
        for i in range(len(level)):
            level[i] = -1
        level[s] = 0
        queue: list[int] = [s]
        head = 0
        while head < len(queue):
            u = queue[head]
            head += 1
            for e in self.graph[u]:
                v, _, cap = e[0], e[1], e[2]
                if cap > 0 and level[v] < 0:
                    level[v] = level[u] + 1
                    queue.append(v)
        return level[t] >= 0

    def _dfs(
        self,
        u: int,
        t: int,
        pushed: int,
        level: list[int],
        it: list[int],
    ) -> int:
        """Send one blocking-flow augment from ``u`` toward ``t``."""
        if u == t:
            return pushed
        while it[u] < len(self.graph[u]):
            e = self.graph[u][it[u]]
            v, rev, cap = e[0], e[1], e[2]
            if cap > 0 and level[v] == level[u] + 1:
                sent = self._dfs(v, t, min(pushed, cap), level, it)
                if sent > 0:
                    e[2] = cap - sent
                    self.graph[v][rev][2] += sent
                    return sent
            it[u] += 1
        return 0

    def max_flow(self, s: int, t: int) -> int:
        """Return the maximum flow from ``s`` to ``t``."""
        level: list[int] = [0] * len(self.graph)
        flow = 0
        while self._bfs(s, t, level):
            it: list[int] = [0] * len(self.graph)
            while True:
                sent = self._dfs(s, t, _INF, level, it)
                if sent == 0:
                    break
                flow += sent
        return flow

    def decompose(self, s: int, t: int, count: int) -> list[list[int]]:
        """Trace ``count`` unit flow paths from ``s`` to ``t``.

        Computes flow on each forward edge as ``cap - residual``, then
        recursively finds s-t paths following remaining flow with
        backtracking. The ``max_flow`` residual is left intact.
        """
        flow_edge: list[list[list[int]]] = [[] for _ in self.graph]
        for (u, v, cap, fwd_idx) in self.forward:
            residual = self.graph[u][fwd_idx][2]
            fwd = cap - residual
            if fwd > 0:
                flow_edge[u].append([v, fwd])

        paths: list[list[int]] = []

        def _walk(u: int) -> list[int] | None:
            """Find a path from ``u`` to sink, or None."""
            if u == t:
                return [t]
            for e in flow_edge[u]:
                v, fwd = e[0], e[1]
                if fwd <= 0:
                    continue
                e[1] = fwd - 1
                tail = _walk(v)
                if tail is not None:
                    return [u] + tail
                e[1] += 1
            return None

        for _ in range(count):
            path = _walk(s)
            if path is None:
                raise RuntimeError(
                    "flow decomposition failed (flow exhausted early)"
                )
            paths.append(path)
        return paths


class _Network:
    """Time-expanded network for one horizon ``T``."""

    def __init__(
        self,
        graph: Graph,
        start: str,
        goal: str,
        n_drones: int,
        t: int,
    ) -> None:
        """Lay out node indices for the given horizon."""
        self.graph = graph
        self.start = start
        self.goal = goal
        self.n_drones = n_drones
        self.t = t

        self.zones = list(graph.zones.keys())
        self.zone_index = {name: i for i, name in enumerate(self.zones)}
        self.links = list(graph.connections.keys())
        self.link_index = {key: i for i, key in enumerate(self.links)}

        nz = len(self.zones)
        nl = len(self.links)
        nt = t + 1  # turns 0..t; real turns are 1..t
        self.src = 0
        self.snk = 1
        self._zone_base = 2
        self._link_base = 2 + nz * nt * 2
        self._n_nodes = self._link_base + nl * nt * 2
        self.dinic = Dinic(self._n_nodes)

    def _zone_in(self, zi: int, turn: int) -> int:
        return self._zone_base + (zi * (self.t + 1) + turn) * 2

    def _zone_out(self, zi: int, turn: int) -> int:
        return self._zone_in(zi, turn) + 1

    def _link_in(self, li: int, turn: int) -> int:
        return self._link_base + (li * (self.t + 1) + turn) * 2

    def _link_out(self, li: int, turn: int) -> int:
        return self._link_in(li, turn) + 1

    def _zone_cap(self, zone_name: str) -> int:
        zone = self.graph.zones[zone_name]
        return _INF if zone.capacity is None else zone.capacity

    def _add_link_chain(
        self, from_node: int, link: tuple[str, str], dep: int, arrive: int
    ) -> int:
        """Chain through per-turn link nodes from ``dep`` to ``arrive-1``.

        The link capacity arcs ``link_in -> link_out`` are added once in
        ``build``; here we only add the connector arcs between turns.
        Returns the node feeding the destination zone.
        """
        g = self.dinic
        li = self.link_index[link]
        prev = from_node
        for tau in range(dep, arrive):
            g.add_edge(prev, self._link_in(li, tau), _INF)
            prev = self._link_out(li, tau)
        return prev

    def build(self) -> None:
        """Construct source, zone, wait, move, and goal arcs."""
        g = self.dinic
        start_zi = self.zone_index[self.start]
        goal_zi = self.zone_index[self.goal]
        t = self.t

        # Link capacity: split each (link, turn) node with a capacity arc.
        for li in range(len(self.links)):
            connection = self.graph.connections[self.links[li]]
            cap = connection.max_link_capacity
            for turn in range(1, t + 1):
                g.add_edge(
                    self._link_in(li, turn),
                    self._link_out(li, turn),
                    cap,
                )

        # Zone capacity: split each (zone, turn) node with a capacity arc.
        for zi in range(len(self.zones)):
            zone_name = self.zones[zi]
            cap = self._zone_cap(zone_name)
            for turn in range(1, t + 1):
                g.add_edge(
                    self._zone_in(zi, turn),
                    self._zone_out(zi, turn),
                    cap,
                )

        # Source injects all drones at (start, 1).
        g.add_edge(self.src, self._zone_in(start_zi, 1), self.n_drones)

        # Wait arcs: occupy the same zone at the next turn.
        for zi in range(len(self.zones)):
            for turn in range(1, t):
                g.add_edge(
                    self._zone_out(zi, turn),
                    self._zone_in(zi, turn + 1),
                    _INF,
                )

        # Move arcs: depart at ``turn``, arrive turn+enter_cost(dest).
        # Waits are expressed by the wait arcs, which compose with this
        # edge to model "wait then move".
        for zi, zone_name in enumerate(self.zones):
            for neighbor in self.graph.neighbors(zone_name):
                nb_zone = self.graph.zones[neighbor]
                cost = _enter_cost(nb_zone)
                if not isinstance(cost, int):
                    continue  # blocked zone
                link = canonical_key(zone_name, neighbor)
                nbi = self.zone_index[neighbor]
                for turn in range(1, t + 1):
                    if turn + cost <= t:
                        prev = self._add_link_chain(
                            self._zone_out(zi, turn),
                            link,
                            turn,
                            turn + cost,
                        )
                        g.add_edge(
                            prev, self._zone_in(nbi, turn + cost), _INF
                        )

        # Sink: arrived drones ride goal wait arcs to T, then exit.
        g.add_edge(self._zone_out(goal_zi, t), self.snk, _INF)


class FlowPlanner:
    """Optimal-makespan planner via quickest flow (homogeneous fleets)."""

    def __init__(self, graph: Graph) -> None:
        """Store the graph for network construction."""
        self.graph = graph

    def plan(self, drones: list[Drone]) -> tuple[Schedule, list[Drone]]:
        """Return a Schedule; mark unreachable drones BLOCKED.

        The schedule is validated for cost-consistency; if the network
        allowed a splice (restricted-zone fast transit) the schedule is
        returned anyway and the caller falls back to CBS.
        """
        if not drones:
            return Schedule(
                actions={}, makespan=0, graph=self.graph
            ), []

        blocked: list[Drone] = []
        start = drones[0].current_zone
        goal = drones[0].target_zone
        if start is None or start not in self.graph.zones or (
            goal not in self.graph.zones
        ):
            for drone in drones:
                self._block(drone)
                blocked.append(drone)
            return Schedule(
                actions={}, makespan=0, graph=self.graph
            ), blocked

        if not self._reachable(start, goal):
            for drone in drones:
                self._block(drone)
                blocked.append(drone)
            return Schedule(
                actions={}, makespan=0, graph=self.graph
            ), blocked

        n = len(drones)
        horizon = 1 + n * sum_entry_cost(self.graph)
        lo, hi = 1, horizon
        while lo < hi:
            mid = (lo + hi) // 2
            if self._max_flow_value(start, goal, mid, n) == n:
                hi = mid
            else:
                lo = mid + 1
        t = lo

        net = _Network(self.graph, start, goal, n, t)
        net.build()
        flow = net.dinic.max_flow(net.src, net.snk)
        if flow != n:
            for drone in drones:
                self._block(drone)
                blocked.append(drone)
            return Schedule(
                actions={}, makespan=0, graph=self.graph
            ), blocked

        paths = net.dinic.decompose(net.src, net.snk, n)
        routes = [self._path_to_route(net, path) for path in paths]
        schedule = _routes_to_schedule(self.graph, drones, routes)
        return schedule, blocked

    def _reachable(self, start: str, goal: str) -> bool:
        """Whether the goal is spatially reachable from start."""
        dist = dist_to_goal(self.graph, goal)
        return dist.get(start, float("inf")) != float("inf")

    def _max_flow_value(
        self, start: str, goal: str, t: int, n: int
    ) -> int:
        """Max-flow value at horizon ``t``."""
        net = _Network(self.graph, start, goal, n, t)
        net.build()
        return net.dinic.max_flow(net.src, net.snk)

    def _path_to_route(
        self, net: _Network, path: list[int]
    ) -> list[tuple[str, int]]:
        """Convert a node path into a TimedRoute truncated at the goal."""
        route: list[tuple[str, int]] = []
        for node in path:
            if node == net.src or node == net.snk:
                continue
            if node < net._link_base:
                offset = node - net._zone_base
                zi = offset // ((net.t + 1) * 2)
                turn = (offset % ((net.t + 1) * 2)) // 2
                if node % 2 == 0:  # zone in node
                    continue
                zone_name = net.zones[zi]
                route.append((zone_name, turn))
                if zone_name == net.goal:
                    return route
        return route

    def _block(self, drone: Drone) -> None:
        """Flag the drone as blocked with a reason."""
        drone.status = DroneStatus.BLOCKED
        drone.blocked_reason = "no route"


def _routes_to_schedule(
    graph: Graph,
    drones: list[Drone],
    routes: list[list[tuple[str, int]]],
) -> Schedule:
    """Build a Schedule, assigning routes to drones by arrival order."""
    from src.models.schedule import ScheduledAction

    ordered = sorted(routes, key=lambda r: (r[-1][1], r))
    actions: dict[int, list[ScheduledAction]] = {}
    makespan = 0
    for drone, route in zip(sorted(drones, key=lambda d: d.id), ordered):
        actions[drone.id] = _route_to_actions(route)
        makespan = max(makespan, route[-1][1])
    return Schedule(actions=actions, makespan=makespan, graph=graph)
