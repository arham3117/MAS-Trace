"""Validate anchor-based true paths against replay-based truth (answers.md D6).

Replay truth for a path: drop its distinguishing edge (the first edge no other candidate
path uses) and check whether the symptom survives. Paths without a distinguishing edge are
`inseparable` and not compared.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from mastrace.analysis.replay import replay
from mastrace.analysis.tracer import Tracer
from mastrace.evaluation.symptom_oracle import make_symptom_check
from mastrace.groundtruth.resolver import resolve
from mastrace.groundtruth.store import GroundTruthStore
from mastrace.provenance.event_graph import EventGraph
from mastrace.settings import Settings


@dataclass(frozen=True)
class PathLabel:
    """One (run, path) comparison."""

    run_id: str
    path: tuple[str, ...]
    anchor_true: bool
    replay_true: bool | None  # necessity: drop this path's distinguishing edge; None = inseparable
    sufficient: bool | None = None  # sufficiency: drop every other path's distinguishing edge

    @property
    def agrees(self) -> bool | None:
        return None if self.replay_true is None else self.anchor_true == self.replay_true


def label_run(run_id: str, settings: Settings) -> list[PathLabel]:
    """Anchor and replay labels for every built_from path of one attacked run."""
    run_dir = settings.runs_dir / run_id
    with GroundTruthStore(settings.ground_truth_path) as s:
        gt = s.get(run_id)
    if gt is None:
        return []
    res = resolve(run_dir, gt, settings)
    if res.symptom_event is None or res.entry_turn is None:
        return []
    graph = EventGraph.from_run(run_dir)
    check = make_symptom_check(gt, settings)
    out = []
    for path in res.causal_paths:
        others = {e for p in res.causal_paths if p != path for e in pairwise(p)}
        dist = next((e for e in pairwise(path) if e not in others), None)
        replay_true: bool | None = None
        if dist is not None:
            drops = Tracer._drops_for_edge(graph, res.entry_turn, res.symptom_event, dist)
            [rid] = replay(run_id, drops, n=1, settings=settings)
            replay_true = not check(rid)
        others_dist = []
        for other in res.causal_paths:
            if other == path:
                continue
            rest = {e for p in res.causal_paths if p != other for e in pairwise(p)}
            od = next((e for e in pairwise(other) if e not in rest), None)
            if od is not None:
                others_dist.append(od)
        drops_all = [
            d
            for od in others_dist
            for d in Tracer._drops_for_edge(graph, res.entry_turn, res.symptom_event, od)
        ]
        [srid] = replay(run_id, drops_all, n=1, settings=settings)
        sufficient = check(srid)
        out.append(PathLabel(run_id, tuple(path), path in res.true_paths, replay_true, sufficient))
    return out


def report(labels: list[PathLabel], title: str) -> str:
    """Markdown summary with both agreements and every (run, path) row."""
    compared = [x for x in labels if x.agrees is not None]
    agree = sum(bool(x.agrees) for x in compared)
    pct = agree / len(compared) if compared else 0.0
    suff = [x for x in labels if x.sufficient is not None]
    s_agree = sum(x.anchor_true == x.sufficient for x in suff)
    s_pct = s_agree / len(suff) if suff else 0.0
    runs = len({x.run_id for x in labels})
    lines = [
        f"# {title}",
        "",
        f"- Runs: {runs}; (run, path) pairs: {len(labels)}; compared: {len(compared)}; "
        f"inseparable: {len(labels) - len(compared)}",
        f"- **Agreement with replay necessity (answers.md D6 rule): {agree}/{len(compared)} "
        f"= {pct:.0%}** (threshold 90%)",
        f"- Agreement with replay sufficiency (alternative, for information): "
        f"{s_agree}/{len(suff)} = {s_pct:.0%}",
        "",
        "Necessity: dropping this path's distinguishing edge removes the symptom. "
        "Sufficiency: with every other path's distinguishing edge dropped, the symptom "
        "still occurs.",
        "",
        "| Run | Path | Anchor-true | Necessary (replay) | Agree | Sufficient (replay) |",
        "|---|---|---|---|---|---|",
    ]
    for x in labels:
        rt = "inseparable" if x.replay_true is None else str(x.replay_true)
        ag = "" if x.agrees is None else ("yes" if x.agrees else "**no**")
        lines.append(
            f"| {x.run_id} | {'→'.join(x.path)} | {x.anchor_true} | {rt} | {ag} | {x.sufficient} |"
        )
    return "\n".join(lines) + "\n"


def write_report(labels: list[PathLabel], path: Path, title: str) -> float:
    """Write the report; return the agreement rate."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report(labels, title), encoding="utf-8")
    compared = [x for x in labels if x.agrees is not None]
    return sum(bool(x.agrees) for x in compared) / len(compared) if compared else 0.0
