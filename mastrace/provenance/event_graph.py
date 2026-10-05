"""Event graph: one node per event, an edge parent → child for every `built_from` entry
(plan.md §7.11, P6.1)."""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Iterable
from pathlib import Path

import networkx as nx

from mastrace.core.schemas import EventKind, EventRecord
from mastrace.provenance.event_store import EventStore


def agent_of(actor: str) -> str | None:
    """`agent:B` → `B`; other actors → None."""
    return actor.removeprefix("agent:") if actor.startswith("agent:") else None


class EventGraph:
    """A DAG over a run's events (an event can only be built from earlier events)."""

    def __init__(self, events: Iterable[EventRecord]) -> None:
        self.events: dict[str, EventRecord] = {}
        self.g: nx.DiGraph[str] = nx.DiGraph()
        for e in events:
            self.events[e.event_id] = e
            self.g.add_node(e.event_id)
            for parent in e.built_from:
                self.g.add_edge(parent, e.event_id)
        self.visits: Counter[str] = Counter()

    @classmethod
    def from_run(cls, run_dir: Path) -> EventGraph:
        """Build from a run's event store."""
        with EventStore.for_run(run_dir, readonly=True) as store:
            return cls(store.iter())

    def is_acyclic(self) -> bool:
        """True if the graph has no cycles (always expected)."""
        return bool(nx.is_directed_acyclic_graph(self.g))

    def ancestors(self, event_id: str) -> dict[str, int]:
        """Every ancestor with its depth (1 = direct parent), via reverse BFS.

        A node is marked visited when it is enqueued, so each node is processed once even
        when several parents lead to it; `visits` counts processing per node.
        """
        depth: dict[str, int] = {}
        queue: deque[tuple[str, int]] = deque([(event_id, 0)])
        seen = {event_id}
        while queue:
            node, d = queue.popleft()
            self.visits[node] += 1
            for parent in sorted(self.g.predecessors(node)):
                if parent not in seen:
                    seen.add(parent)
                    depth[parent] = d + 1
                    queue.append((parent, d + 1))
        return depth

    def descendants(self, event_id: str) -> set[str]:
        """Every event built (transitively) from `event_id`."""
        return set(nx.descendants(self.g, event_id))

    def turn_events(self, turn_id: str) -> list[str]:
        """IDs of the events recorded inside a turn, in seq order."""
        return [
            i
            for i, e in sorted(self.events.items(), key=lambda kv: kv[1].seq)
            if e.turn_id == turn_id
        ]

    def simple_paths(self, src_turn: str, dst_event: str) -> list[list[str]]:
        """Agent sequences along which content of `src_turn` reaches `dst_event`.

        Only `message` events that descend from the turn and are ancestors of the destination
        count as hops, so every returned path is a causal chain of messages.
        """
        src_agent = src_turn.split("#")[0]
        dst_agent = agent_of(self.events[dst_event].actor)
        if dst_agent is None:
            return []
        reach: set[str] = set()
        for tid in self.turn_events(src_turn):
            reach |= self.descendants(tid) | {tid}
        causal = reach & (set(nx.ancestors(self.g, dst_event)) | {dst_event})
        hops: nx.DiGraph[str] = nx.DiGraph()
        hops.add_nodes_from([src_agent, dst_agent])
        for eid in sorted(causal):
            ev = self.events[eid]
            sender = agent_of(ev.actor)
            if ev.kind == EventKind.MESSAGE and sender and ev.receivers:
                hops.add_edge(sender, ev.receivers[0])
        if src_agent == dst_agent:
            return [[src_agent]]
        return sorted(nx.all_simple_paths(hops, src_agent, dst_agent))
