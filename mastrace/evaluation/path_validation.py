"""Three ground-truth labels per path, and their validation (answers.md D6, ISSUE-025).

- carried: every hop of the path, and the symptom, contain an anchor (`true_paths`).
- sufficient: a replay that blocks every other path's distinguishing edge (keeps only this
  path) still produces the symptom.
- necessary: a replay that drops this path's distinguishing edge removes the symptom.

Validation compares carried with sufficient (bar 90%). Under redundancy no path is
necessary, so "necessary" is reported separately and is not a validation reference.
Paths without a distinguishing edge are `inseparable` for the necessity test.
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
    def carried(self) -> bool:
        return self.anchor_true

    @property
    def necessary(self) -> bool | None:
        return self.replay_true

    @property
    def agrees(self) -> bool | None:
        """carried vs sufficient (the validation reference, ISSUE-025)."""
        return None if self.sufficient is None else self.anchor_true == self.sufficient


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
    """Markdown summary: carried vs sufficient (validation), plus the necessity view."""
    compared = [x for x in labels if x.agrees is not None]
    agree = sum(bool(x.agrees) for x in compared)
    pct = agree / len(compared) if compared else 0.0
    nec = [x for x in labels if x.necessary is not None]
    n_agree = sum(x.carried == x.necessary for x in nec)
    by_run: dict[str, list[PathLabel]] = {}
    for x in labels:
        by_run.setdefault(x.run_id, []).append(x)
    over = sum(
        1
        for xs in by_run.values()
        if sum(bool(x.sufficient) for x in xs) >= 2 and not any(x.necessary for x in xs)
    )
    lines = [
        f"# {title}",
        "",
        f"- Runs: {len(by_run)}; (run, path) pairs: {len(labels)}",
        f"- **Validation, carried vs sufficient: {agree}/{len(compared)} = {pct:.0%}** "
        "(bar 90%, ISSUE-025)",
        f"- For information, carried vs necessary: {n_agree}/{len(nec)} "
        f"(not a valid reference under redundancy)",
        f"- Overdetermined runs (≥ 2 sufficient paths, none necessary): {over}/{len(by_run)}",
        "",
        "| Run | Path | Carried | Sufficient | Necessary | Responsibility | Agree |",
        "|---|---|---|---|---|---|---|",
    ]
    for run, xs in by_run.items():
        m = sum(bool(x.sufficient) for x in xs)
        for x in xs:
            resp = f"{1 / m:.2f}" if x.sufficient and m else "0"
            nec_s = "inseparable" if x.necessary is None else str(x.necessary)
            ag = "" if x.agrees is None else ("yes" if x.agrees else "**no**")
            lines.append(
                f"| {run} | {'→'.join(x.path)} | {x.carried} | {x.sufficient} | {nec_s} | "
                f"{resp} | {ag} |"
            )
    return "\n".join(lines) + "\n"


def write_report(labels: list[PathLabel], path: Path, title: str) -> float:
    """Write the report; return the agreement rate."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report(labels, title), encoding="utf-8")
    compared = [x for x in labels if x.agrees is not None]
    return sum(bool(x.agrees) for x in compared) / len(compared) if compared else 0.0
