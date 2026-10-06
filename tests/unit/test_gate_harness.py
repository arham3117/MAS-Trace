"""answers.md D1d/D1f/D1g: real-model check sampling, G2 fallback, propagation table."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastrace.control import gates
from mastrace.core.schemas import Verdict
from mastrace.runtime.run import RunResult
from mastrace.settings import Settings
from tests.gates import harness
from tests.gates.harness import MODEL_PAIRS, Lab, model_check, sample_goal


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lab:
    monkeypatch.setattr(harness, "RESULTS", tmp_path / "_current.jsonl")
    return Lab(Settings(data_dir=tmp_path / "data"))


def ok(r: RunResult, v: Verdict) -> bool:
    return v.entry_turn == "A#1"


def test_pairs_are_tasks_then_seeds() -> None:
    assert MODEL_PAIRS[:3] == [("t01", 1), ("t01", 2), ("t02", 1)] and len(MODEL_PAIRS) == 20


def test_g1_decides_when_it_lands(lab: Lab) -> None:
    assert model_check(lab, "X", "s1_chain", ok, model="scripted_gullible")
    lines = [json.loads(x) for x in harness.RESULTS.read_text().splitlines()]
    check = next(x for x in lines if "check" in x)
    assert check["result"] == "PASS" and "decided by G1" in check["notes"]
    assert "G2" not in check["notes"]
    assert sum(x.get("type") == "propagation" for x in lines) == 5


def test_g2_fallback_used_when_g1_cannot_land(lab: Lab, monkeypatch: pytest.MonkeyPatch) -> None:
    real_trace = Lab.trace

    def trace(self: Lab, r: RunResult) -> Verdict | None:
        return None if "-g1s" in r.run_id else real_trace(self, r)  # G1 never symptomatic

    monkeypatch.setattr(Lab, "trace", trace)
    assert model_check(lab, "X", "s1_chain", ok, model="scripted_gullible")
    check = next(json.loads(x) for x in harness.RESULTS.read_text().splitlines() if "check" in x)
    assert "G1: 0/20 symptomatic" in check["notes"] and "decided by G2" in check["notes"]


def test_inconclusive_when_nothing_lands(lab: Lab, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Lab, "trace", lambda self, r: None)
    monkeypatch.setattr(harness, "MODEL_PAIRS", MODEL_PAIRS[:2])
    assert not model_check(lab, "X", "s1_chain", ok, model="scripted_resistant")
    check = next(json.loads(x) for x in harness.RESULTS.read_text().splitlines() if "check" in x)
    assert check["result"] == "INCONCLUSIVE"


def test_sample_goal_stops_at_five(lab: Lab) -> None:
    g = sample_goal(lab, "s1_chain", "G1", ok, model="scripted_gullible")
    assert (g.symptomatic, g.tried, g.correct) == (5, 5, 5)


def test_propagation_table() -> None:
    hops = {h: {"anchor": h in "AB", "overlap": h == "A", "jaccard": 0.3} for h in gates.HOPS}
    rows = [{"type": "propagation", "config": "s1_chain", "goal": "G1", "hops": hops}] * 2
    table = "\n".join(gates.propagation_table(rows))
    assert "| s1_chain | G1 | 2 | 100% / 100% | 100% / 0% | 0% / 0% |" in table
