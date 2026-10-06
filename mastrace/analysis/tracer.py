"""Tracer v1: from a symptom back to the event, agent and turn where the attack entered
(plan.md §7.11, P7.2). Plain code; replay confirms every conclusion (no AI, I2)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations, pairwise
from pathlib import Path
from typing import Any

import networkx as nx
import yaml

from mastrace.analysis.detectors import Detectors
from mastrace.analysis.replay import replay
from mastrace.core.ids import parse_turn_id
from mastrace.core.schemas import (
    DropMessageOverride,
    EventKind,
    EventRecord,
    Override,
    ToolOutputOverride,
    Verdict,
)
from mastrace.environment.tasks import load_task
from mastrace.provenance.event_graph import EventGraph, agent_of
from mastrace.provenance.event_store import EventStore
from mastrace.provenance.payload_store import PayloadStore
from mastrace.runtime.run import read_manifest
from mastrace.settings import REPO_ROOT, Settings, get_settings, load_model

TRACER_CONFIG = REPO_ROOT / "configs" / "tracer.yaml"
SymptomCheck = Callable[[str], bool]


@dataclass(frozen=True)
class TracerConfig:
    """`configs/tracer.yaml`."""

    top_k: int = 3
    replays_scripted: int = 1
    replays_real: int = 3
    w_overlap: float = 0.6
    w_pattern: float = 0.4
    ngram: int = 5
    max_paths: int = 5
    neutral: str = "[content unavailable]"

    @classmethod
    def load(cls, path: Path = TRACER_CONFIG) -> TracerConfig:
        """Read the YAML config."""
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            top_k=raw["top_k"],
            replays_scripted=raw["replays_per_candidate"]["scripted"],
            replays_real=raw["replays_per_candidate"]["real"],
            w_overlap=raw["weights"]["overlap"],
            w_pattern=raw["weights"]["pattern"],
            ngram=raw["ngram"],
            max_paths=raw["max_paths"],
            neutral=raw["neutral_replacement"],
        )


def ngrams(text: str, n: int) -> set[str]:
    """Character n-grams of whitespace-normalized, lower-cased text."""
    t = " ".join(text.lower().split())
    return {t[i : i + n] for i in range(max(len(t) - n + 1, 0))}


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity: shared n-grams over all n-grams (0 for two empty sets)."""
    return len(a & b) / len(a | b) if a | b else 0.0


def is_candidate(e: EventRecord) -> bool:
    """Entry candidates: external reads, internal tool reads, memory reads (§7.11 step 3)."""
    if e.kind in (EventKind.EXTERNAL_READ, EventKind.MEMORY_READ):
        return True
    return e.kind == EventKind.TOOL_CALL and e.meta.get("source") == "internal"


def select_entries(graph: EventGraph, confirmed: Sequence[str]) -> list[str]:
    """Keep the most upstream confirmed candidates (ISSUE-024, general rule).

    A confirmed candidate that descends from another confirmed candidate is a consequence
    of that entry (for example a file read the attacker's text asked for), not an entry
    point. Order (ranking) is preserved.
    """
    out = []
    for c in confirmed:
        if not any(o != c and c in graph.descendants(o) for o in confirmed):
            out.append(c)
    return out


class Tracer:
    """Plain-code tracer. Reads the run log; never reads ground truth (I8)."""

    def __init__(self, settings: Settings | None = None, config: TracerConfig | None = None):
        self.settings = settings or get_settings()
        self.cfg = config or TracerConfig.load()

    def trace(self, run_id: str, symptom_event_id: str, symptom_check: SymptomCheck) -> Verdict:
        """Diagnose one symptom and store the verdict in the run's `verdicts` table."""
        run_dir = self.settings.runs_dir / run_id
        manifest = read_manifest(run_dir)
        graph = EventGraph.from_run(run_dir)
        payloads = PayloadStore(run_dir / "payloads")
        n = (
            self.cfg.replays_scripted
            if load_model(manifest.model_key, self.settings.models_config).provider == "scripted"
            else self.cfg.replays_real
        )
        task = load_task(manifest.task_id, self.settings.templates_dir)
        detectors = Detectors(task.allowed_recipients, payloads)

        ancestors = graph.ancestors(symptom_event_id)
        ranking = self._rank(graph, payloads, detectors, symptom_event_id, ancestors)

        replays: list[dict[str, Any]] = []
        confirmed: list[str] = []
        top = [graph.events[c["candidate"]] for c in ranking[: self.cfg.top_k]]
        for e in top:
            override = self._neutralize(e)
            ids, present = self._replay(run_id, [override], n, symptom_check)
            ok = sum(present) * 2 < len(present)  # symptom gone in the majority
            replays.append(
                {
                    "kind": "candidate",
                    "candidate": e.event_id,
                    "override": override.model_dump(mode="json"),
                    "replay_run_ids": ids,
                    "symptom_present": present,
                    "confirmed": ok,
                }
            )
            if ok:
                confirmed.append(e.event_id)
        # An entry point is where attacker content came in from outside. A confirmed
        # candidate downstream of another confirmed candidate is a consequence of it
        # (select_entries). If every remaining confirmed candidate was reached through a
        # message from another top candidate ("derived"), the true entries did not confirm
        # on their own (independent causes), so pairs are tried.
        confirmed = select_entries(graph, confirmed)
        derived = {e.event_id for e in top if self._derived(graph, e, top)}
        upstream = [c for c in confirmed if c not in derived]
        if upstream:
            confirmed = upstream
        else:
            # P11.2: independent causes. Neutralizing one entry leaves the other, so try
            # pairs of non-derived candidates; a pair that removes the symptom confirms both.
            for a, b in combinations([e for e in top if e.event_id not in derived], 2):
                overrides = [self._neutralize(a), self._neutralize(b)]
                ids, present = self._replay(run_id, overrides, n, symptom_check)
                ok = sum(present) * 2 < len(present)
                replays.append(
                    {
                        "kind": "candidate_set",
                        "candidates": [a.event_id, b.event_id],
                        "overrides": [o.model_dump(mode="json") for o in overrides],
                        "replay_run_ids": ids,
                        "symptom_present": present,
                        "confirmed": ok,
                    }
                )
                if ok:
                    confirmed = [a.event_id, b.event_id]
                    break

        with EventStore.for_run(run_dir, readonly=True) as store:
            k = len(store.verdicts()) + 1
        verdict_id = f"{run_id}:tracer_v1:{symptom_event_id}:{k}"
        base: dict[str, Any] = {
            "verdict_id": verdict_id,
            "run_id": run_id,
            "method": "tracer_v1",
            "symptom_event_id": symptom_event_id,
            "ranking": ranking,
            "confirmed_entry_events": confirmed,
        }
        if not confirmed:
            v = Verdict(status="unconfirmed", replays=replays, **base)
        else:
            entry = confirmed[0]
            entry_turn = self._entry_turn(graph, entry)
            paths, path_replays = self._paths(
                run_id, graph, entry_turn, symptom_event_id, manifest.stage, n, symptom_check
            )
            replays += path_replays
            v = Verdict(
                status="confirmed",
                entry_event_id=entry,
                entry_agent=entry_turn.split("#")[0],
                entry_turn=entry_turn,
                paths=paths,
                replays=replays,
                **base,
            )
        v.replays_used = sum(len(r["replay_run_ids"]) for r in v.replays)
        v.tokens_used = sum(self._tokens(rid) for r in v.replays for rid in r["replay_run_ids"])
        with EventStore.for_run(run_dir) as store:
            store.add_verdict(v)
        return v

    # -- steps ---------------------------------------------------------------------

    def _rank(
        self,
        graph: EventGraph,
        payloads: PayloadStore,
        detectors: Detectors,
        symptom: str,
        ancestors: dict[str, int],
    ) -> list[dict[str, Any]]:
        def text(e: EventRecord, both: bool = False) -> str:
            parts = [e.output_ref] + ([e.input_ref] if both else [])
            return "\n".join(payloads.get(r) for r in parts if r)

        sym = graph.events[symptom]
        context = [text(sym, both=True)] + [
            text(graph.events[a])
            for a in sorted(ancestors)
            if graph.events[a].kind == EventKind.MESSAGE
        ]
        target = ngrams("\n".join(context), self.cfg.ngram)
        rows: list[dict[str, Any]] = []
        for eid, depth in ancestors.items():
            e = graph.events[eid]
            if not is_candidate(e):
                continue
            body = text(e)
            overlap = jaccard(ngrams(body, self.cfg.ngram), target)
            pattern = 1.0 if detectors.injection_match(body) else 0.0
            rows.append(
                {
                    "candidate": eid,
                    "kind": e.kind.value,
                    "turn_id": e.turn_id,
                    "score": round(self.cfg.w_overlap * overlap + self.cfg.w_pattern * pattern, 6),
                    "overlap": round(overlap, 6),
                    "pattern": pattern,
                    "depth": depth,
                    "seq": e.seq,
                }
            )
        rows.sort(key=lambda r: (-r["score"], -r["depth"], r["seq"]))
        return rows

    @staticmethod
    def _derived(graph: EventGraph, e: EventRecord, others: Sequence[EventRecord]) -> bool:
        """True if another candidate reaches `e` through at least one message event."""
        anc = nx.ancestors(graph.g, e.event_id)
        messages = [m for m in anc if graph.events[m].kind == EventKind.MESSAGE]
        for other in others:
            if other.event_id == e.event_id or other.event_id not in anc:
                continue
            reach = nx.descendants(graph.g, other.event_id)
            if any(m in reach for m in messages):
                return True
        return False

    def _neutralize(self, e: EventRecord) -> ToolOutputOverride:
        agent, turn = parse_turn_id(str(e.turn_id))
        return ToolOutputOverride(
            agent=agent, turn=turn, call_index=int(e.call_index or 0), replacement=self.cfg.neutral
        )

    def _replay(
        self, run_id: str, overrides: Sequence[Override], n: int, check: SymptomCheck
    ) -> tuple[list[str], list[bool]]:
        ids = replay(run_id, overrides, n=n, settings=self.settings)
        return ids, [check(rid) for rid in ids]

    @staticmethod
    def _entry_turn(graph: EventGraph, entry: str) -> str:
        """The turn of the first model call that had the entry event in its prompt."""
        users = sorted(
            (
                graph.events[c]
                for c in graph.g.successors(entry)
                if graph.events[c].kind == EventKind.MODEL_CALL
            ),
            key=lambda e: e.seq,
        )
        return str(users[0].turn_id if users else graph.events[entry].turn_id)

    def _paths(
        self,
        run_id: str,
        graph: EventGraph,
        entry_turn: str,
        symptom: str,
        stage: int,
        n: int,
        check: SymptomCheck,
    ) -> tuple[list[list[str]], list[dict[str, Any]]]:
        all_paths = graph.simple_paths(entry_turn, symptom)
        if stage in (1, 2):
            if not all_paths:
                return [], []
            return [min(all_paths, key=lambda p: (len(p), p))], []
        paths = all_paths[: self.cfg.max_paths]
        dist: dict[tuple[str, ...], tuple[str, str] | None] = {}
        for path in paths:
            others = {e for p in paths if p != path for e in pairwise(p)}
            dist[tuple(path)] = next((e for e in pairwise(path) if e not in others), None)
        results: list[dict[str, Any]] = []
        for path in paths:
            d = dist[tuple(path)]
            if d is None:
                results.append(
                    {"kind": "path", "path": path, "status": "inseparable", "replay_run_ids": []}
                )
                continue
            drops = self._drops_for_edge(graph, entry_turn, symptom, d)
            ids, present = self._replay(run_id, drops, n, check)
            necessary = sum(present) * 2 < len(present)
            results.append(
                {
                    "kind": "path",
                    "path": path,
                    "edge": list(d),
                    "overrides": [o.model_dump(mode="json") for o in drops],
                    "replay_run_ids": ids,
                    "symptom_present": present,
                    "status": "necessary" if necessary else "non_causal",
                }
            )
        if results and not any(r["status"] == "necessary" for r in results):
            # Overdetermined symptom: no single path is necessary. Keep only one path at a
            # time (block every other path's distinguishing edge); if the symptom survives,
            # the path is sufficient on its own: "redundant".
            for r in results:
                if r["status"] == "inseparable":
                    continue
                keep = tuple(r["path"])
                blocks = [
                    o
                    for p, e in dist.items()
                    if p != keep and e is not None
                    for o in self._drops_for_edge(graph, entry_turn, symptom, e)
                ]
                ids, present = self._replay(run_id, blocks, n, check)
                sufficient = sum(present) * 2 > len(present)
                r["keep_only"] = {
                    "overrides": [o.model_dump(mode="json") for o in blocks],
                    "replay_run_ids": ids,
                    "symptom_present": present,
                }
                r["replay_run_ids"] = r["replay_run_ids"] + ids
                r["status"] = "redundant" if sufficient else "non_causal"
        return paths, results

    @staticmethod
    def _drops_for_edge(
        graph: EventGraph, entry_turn: str, symptom: str, edge: tuple[str, str]
    ) -> list[Override]:
        """Drop every causal message on `edge`, addressed by its attempt number."""
        reach: set[str] = set()
        for t in graph.turn_events(entry_turn):
            reach |= graph.descendants(t)
        causal = reach & graph.ancestor_set(symptom)
        attempts = 0
        drops: list[Override] = []
        for e in sorted(graph.events.values(), key=lambda e: e.seq):
            sender = agent_of(e.actor) if e.kind == EventKind.MESSAGE else e.meta.get("from")
            if e.kind not in (EventKind.MESSAGE, EventKind.ROUTER_REJECT):
                continue
            if (sender, e.receivers[0] if e.receivers else None) != edge:
                continue
            attempts += 1
            if e.kind == EventKind.MESSAGE and e.event_id in causal:
                drops.append(
                    DropMessageOverride.model_validate(
                        {"from": edge[0], "to": edge[1], "nth": attempts}
                    )
                )
        return drops

    def _tokens(self, run_id: str) -> int:
        with EventStore.for_run(self.settings.runs_dir / run_id, readonly=True) as s:
            summary = s.summary() or {}
        return int(summary.get("tokens", 0))


def detector_check(detector: str, settings: Settings) -> SymptomCheck:
    """Live-mode symptom check: did the same detector fire in the replay?"""

    def check(run_id: str) -> bool:
        with EventStore.for_run(settings.runs_dir / run_id, readonly=True) as s:
            return any(a.detector == detector for a in s.alerts())

    return check
