"""Stage 3 gate (mixed links): G3-1, G3-2 (plan.md §9.2)."""

from __future__ import annotations

import pytest

from mastrace.core.schemas import Verdict
from mastrace.runtime.run import RunResult
from tests.gates.harness import SCRIPTED_RUNS, Lab, model_check, record

pytestmark = [pytest.mark.gate]
BOTH = [["A", "B", "C", "E"], ["A", "B", "D", "E"]]


@pytest.mark.plumbing
def test_g3_1_finds_every_path(lab: Lab) -> None:
    ok, ids = 0, []
    for t, s in SCRIPTED_RUNS:
        r = lab.run("s3_mixed_two_paths", t, "g1s0", "scripted_gullible", s)
        v = lab.trace(r)
        ids.append(r.run_id)
        ok += v is not None and sorted(v.paths) == BOTH
    assert record("G3-1", ok, 5, 5, runs=ids)


def causal_ok(r: RunResult, v: Verdict) -> bool:
    marks = {tuple(x["path"]): x["status"] for x in v.replays if x["kind"] == "path"}
    return (
        marks.get(("A", "B", "D", "E")) == "causal"
        and marks.get(("A", "B", "C", "E")) == "non_causal"
    )


@pytest.mark.plumbing
def test_g3_2_picks_causal_path(lab: Lab) -> None:
    ok, ids = 0, []
    for t, s in SCRIPTED_RUNS:
        r = lab.run(
            "s3_mixed_two_paths",
            t,
            "g1s0",
            "scripted_gullible",
            s,
            policy_overrides={"C": "resistant"},
        )
        v = lab.trace(r)
        ids.append(r.run_id)
        ok += v is not None and causal_ok(r, v)
    assert record("G3-2[scripted]", ok, 5, 5, runs=ids)


@pytest.mark.model
@pytest.mark.slow
def test_g3_2_dev_open(lab: Lab) -> None:
    ok, n, ids, inconclusive = model_check(lab, "s3_mixed_two_paths", "g1s0", causal_ok)
    assert record("G3-2[dev_open]", ok, n, 4, f"{n} symptomatic of ≤15 seeds", ids, inconclusive)
