"""Stage 2 gate (two-way links): G2-1 … G2-3 (plan.md §9.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mastrace.core.schemas import GraphConfig, Verdict
from mastrace.runtime.graph_config import load_graph
from mastrace.runtime.run import RunResult
from tests.gates.harness import SCRIPTED_RUNS, STAGE_CONFIGS, Lab, model_check, record

pytestmark = [pytest.mark.gate]
TASKS = [f"t{i:02d}" for i in range(1, 11)]


def stress_config() -> GraphConfig:
    """Two-way chain allowing 4 messages per direction, for 3 feedback rounds."""
    cfg = load_graph("s2_two_way_chain").model_copy(deep=True)
    cfg.limits.max_messages_per_direction = 4
    return cfg


@pytest.mark.plumbing
def test_g2_1_conversations_stop(lab: Lab) -> None:
    ok, ids, bad = 0, [], []
    for config in STAGE_CONFIGS[2]:
        cfg = load_graph(config)
        for t in TASKS:
            r = lab.run(config, t, None, "scripted_gullible", 1)
            ids.append(r.run_id)
            within = (
                r.supersteps <= cfg.limits.max_supersteps
                and r.tokens_used <= cfg.limits.max_tokens_run
            )
            if r.status != "crashed" and within:
                ok += 1
            else:
                bad.append(f"{r.run_id}:{r.status}")
    assert record("G2-1", ok, len(ids), len(ids), "; ".join(bad), ids)


@pytest.mark.plumbing
def test_g2_2_tracer_finishes_on_long_conversations(
    lab: Lab, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mastrace.provenance import event_graph

    graphs: list[event_graph.EventGraph] = []
    orig = event_graph.EventGraph.from_run.__func__  # type: ignore[attr-defined]

    def spy(cls: type, run_dir: Path) -> event_graph.EventGraph:
        g: event_graph.EventGraph = orig(cls, run_dir)
        graphs.append(g)
        return g

    monkeypatch.setattr(event_graph.EventGraph, "from_run", classmethod(spy))
    ok, ids, notes = 0, [], []
    for t, s in SCRIPTED_RUNS:
        r = lab.run(stress_config(), t, "g1s0", "scripted_gullible", s, feedback_rounds=3)
        graphs.clear()
        v = lab.trace(r)
        per_dir = max(e.link["count"] for e in lab.events(r) if e.link)
        traversed = [g for g in graphs if g.visits]
        once = bool(traversed) and all(max(g.visits.values()) == 1 for g in traversed)
        ids.append(r.run_id)
        notes.append(f"max/dir={per_dir}")
        ok += v is not None and v.entry_turn == "A#1" and once and per_dir >= 3
    assert record("G2-2", ok, 5, 5, ", ".join(notes), ids)


def two_way_ok(r: RunResult, v: Verdict) -> bool:
    return v.status == "confirmed" and v.entry_agent == "A" and v.entry_turn == "A#1"


@pytest.mark.plumbing
def test_g2_3_culprit_after_back_and_forth(lab: Lab) -> None:
    ok, ids = 0, []
    for t, s in SCRIPTED_RUNS:
        r = lab.run(stress_config(), t, "g1s0", "scripted_gullible", s, feedback_rounds=3)
        v = lab.trace(r)
        ids.append(r.run_id)
        ok += v is not None and two_way_ok(r, v)
    assert record("G2-3[scripted]", ok, 5, 5, runs=ids)


@pytest.mark.model
@pytest.mark.slow
def test_g2_3_dev_open(lab: Lab) -> None:
    assert model_check(lab, "G2-3[dev_open]", "s2_two_way_chain", two_way_ok)
