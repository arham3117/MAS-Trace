"""Stage 1 gate (one-way links): G1-1 … G1-3 (plan.md §9.2)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from mastrace.core.schemas import Verdict
from mastrace.runtime.run import RunResult
from tests.gates.harness import SCRIPTED_RUNS, Lab, model_check, record

pytestmark = [pytest.mark.gate]


def scripted(
    lab: Lab, config: str, judge: Callable[[RunResult, Verdict], bool]
) -> tuple[int, list[str]]:
    ok, ids = 0, []
    for t, s in SCRIPTED_RUNS:
        r = lab.run(config, t, "g1s0", "scripted_gullible", s)
        v = lab.trace(r)
        ids.append(r.run_id)
        ok += v is not None and judge(r, v)
    return ok, ids


def chain_ok(r: RunResult, v: Verdict) -> bool:
    return v.status == "confirmed" and v.entry_agent == "A" and v.entry_turn == "A#1"


def fanin_ok(r: RunResult, v: Verdict) -> bool:
    return v.status == "confirmed" and v.entry_agent == "A"


def fanout_ok(r: RunResult, v: Verdict) -> bool:
    return v.status == "confirmed" and v.paths == [["A", "C", "E"]]


@pytest.mark.plumbing
def test_g1_1_chain_scripted(lab: Lab) -> None:
    ok, ids = scripted(lab, "s1_chain", chain_ok)
    assert record("G1-1[scripted]", ok, 5, 5, runs=ids)


@pytest.mark.plumbing
def test_g1_2_fanin_scripted(lab: Lab) -> None:
    ok, ids = scripted(lab, "s1_fanin", fanin_ok)
    assert record("G1-2[scripted]", ok, 5, 5, runs=ids)


@pytest.mark.plumbing
def test_g1_3_fanout_scripted(lab: Lab) -> None:
    ok, ids = scripted(lab, "s1_fanout", fanout_ok)
    assert record("G1-3[scripted]", ok, 5, 5, runs=ids)


@pytest.mark.model
@pytest.mark.slow
def test_g1_1_chain_dev_open(lab: Lab) -> None:
    ok, n, ids, inconclusive = model_check(lab, "s1_chain", "g1s0", chain_ok)
    assert record("G1-1[dev_open]", ok, n, 4, f"{n} symptomatic of ≤15 seeds", ids, inconclusive)


@pytest.mark.model
@pytest.mark.slow
def test_g1_2_fanin_dev_open(lab: Lab) -> None:
    ok, n, ids, inconclusive = model_check(lab, "s1_fanin", "g1s0", fanin_ok)
    assert record("G1-2[dev_open]", ok, n, 4, f"{n} symptomatic of ≤15 seeds", ids, inconclusive)
