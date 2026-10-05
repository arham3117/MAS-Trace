"""Shared machinery for the gate suites (plan.md §9)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mastrace.analysis.tracer import Tracer
from mastrace.control.controller import run_with_attack
from mastrace.core.schemas import EventKind, GraphConfig, GroundTruth, Verdict
from mastrace.evaluation.symptom_oracle import make_symptom_check, symptom_event
from mastrace.groundtruth.store import GroundTruthStore
from mastrace.provenance.event_store import EventStore
from mastrace.runtime.run import RunResult
from mastrace.settings import REPO_ROOT, Settings

RESULTS = REPO_ROOT / "reports" / "gates" / "_current.jsonl"
STAGE_CONFIGS = {
    1: ["s1_chain", "s1_fanin", "s1_fanout"],
    2: ["s2_two_way_chain", "s2_two_way_mesh"],
    3: ["s3_mixed_two_paths", "s3_whiteboard"],
}
SCRIPTED_RUNS = [(f"t{i:02d}", i) for i in range(1, 6)]  # (task, seed): t01/s1 … t05/s5
MODEL_MAX_SEEDS = 15
MODEL_NEEDED = 5


def gate_stage() -> int:
    """Stage under test (`MASTRACE_GATE_STAGE`, default 1)."""
    return int(os.environ.get("MASTRACE_GATE_STAGE", "1"))


def configs_upto(stage: int) -> list[str]:
    """Configs of the given stage and every earlier one."""
    return [c for s in sorted(STAGE_CONFIGS) if s <= stage for c in STAGE_CONFIGS[s]]


def record(
    check: str,
    passed: int,
    total: int,
    required: int,
    notes: str = "",
    runs: list[str] | None = None,
    inconclusive: bool = False,
) -> bool:
    """Append one check result to `reports/gates/_current.jsonl`; return pass/fail."""
    ok = (not inconclusive) and passed >= required
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "check": check,
                    "passed": passed,
                    "total": total,
                    "required": required,
                    "result": "INCONCLUSIVE" if inconclusive else ("PASS" if ok else "FAIL"),
                    "notes": notes,
                    "runs": runs or [],
                }
            )
            + "\n"
        )
    return ok


@dataclass
class Lab:
    """Runs and traces inside one gate session's data directory (memoized)."""

    settings: Settings
    _runs: dict[tuple[Any, ...], RunResult] = field(default_factory=dict)

    def run(
        self,
        config: str | GraphConfig,
        task: str,
        attack: str | None,
        model: str,
        seed: int,
        **kw: Any,
    ) -> RunResult:
        cfg_key = config if isinstance(config, str) else config.model_dump_json()
        key = (cfg_key, task, attack, model, seed, repr(sorted(kw.items())))
        if key not in self._runs:
            self._runs[key] = run_with_attack(
                config, task, attack, model, seed, settings=self.settings, overwrite=True, **kw
            )
        return self._runs[key]

    def gt(self, run_id: str) -> GroundTruth | None:
        with GroundTruthStore(self.settings.ground_truth_path) as s:
            return s.get(run_id)

    def symptom(self, r: RunResult) -> str | None:
        return symptom_event(r.run_dir, self.gt(r.run_id), self.settings)

    def trace(self, r: RunResult) -> Verdict | None:
        """Trace the run's oracle symptom; None if the attack did not land."""
        sid = self.symptom(r)
        gt = self.gt(r.run_id)
        if sid is None or gt is None:
            return None
        return Tracer(self.settings).trace(r.run_id, sid, make_symptom_check(gt, self.settings))

    def events(self, r: RunResult) -> list[Any]:
        with EventStore.for_run(r.run_dir, readonly=True) as s:
            return list(s.iter())

    def alerts(self, r: RunResult) -> list[Any]:
        with EventStore.for_run(r.run_dir, readonly=True) as s:
            return s.alerts()

    def verdicts(self, r: RunResult) -> list[Verdict]:
        with EventStore.for_run(r.run_dir, readonly=True) as s:
            return s.verdicts()


def log_complete(lab: Lab, r: RunResult) -> bool:
    """G-C1: instrumented counters equal the events in the store."""
    ev = lab.events(r)

    def n(*kinds: EventKind) -> int:
        return sum(e.kind in kinds for e in ev)

    return (
        r.stats["model_calls"] == n(EventKind.MODEL_CALL)
        and r.stats["tool_calls"]
        == n(
            EventKind.TOOL_CALL,
            EventKind.EXTERNAL_READ,
            EventKind.MEMORY_READ,
            EventKind.MEMORY_WRITE,
        )
        and r.stats["router_messages"] == n(EventKind.MESSAGE, EventKind.ROUTER_REJECT)
    )


def model_check(
    lab: Lab,
    config: str,
    attack: str,
    judge: Callable[[RunResult, Verdict], bool],
    model: str = "dev_open",
    **kw: Any,
) -> tuple[int, int, list[str], bool]:
    """§9.3: seeds 1.. (task t01-t05 in turn) until 5 symptomatic runs, at most 15 seeds.

    Returns (correct, symptomatic, run_ids, inconclusive).
    """
    correct = symptomatic = 0
    ids: list[str] = []
    for seed in range(1, MODEL_MAX_SEEDS + 1):
        task = f"t{(seed - 1) % 5 + 1:02d}"
        r = lab.run(config, task, attack, model, seed, **kw)
        v = lab.trace(r)
        if v is None:
            continue
        symptomatic += 1
        ids.append(r.run_id)
        correct += judge(r, v)
        if symptomatic == MODEL_NEEDED:
            break
    return correct, symptomatic, ids, symptomatic < MODEL_NEEDED
