"""Gate checks run at every stage: G-C1 … G-C5 (plan.md §9.1)."""

from __future__ import annotations

import pytest

from mastrace.analysis.replay import replay
from tests.gates.harness import SCRIPTED_RUNS, Lab, configs_upto, gate_stage, log_complete, record
from tests.netguard import NetworkGuard

pytestmark = [pytest.mark.gate]
CONFIGS = configs_upto(gate_stage())


def sig(lab: Lab, run_id: str) -> list[tuple[object, ...]]:
    r = lab.settings.runs_dir / run_id
    from mastrace.provenance.event_store import EventStore

    with EventStore.for_run(r, readonly=True) as s:
        return [(e.kind, e.actor, e.turn_id, e.input_ref, e.output_ref) for e in s.iter()]


@pytest.mark.plumbing
@pytest.mark.parametrize("config", CONFIGS)
def test_gc1_log_complete(lab: Lab, config: str) -> None:
    runs = [lab.run(config, t, "g1s0", "scripted_gullible", s) for t, s in SCRIPTED_RUNS]
    ok = sum(log_complete(lab, r) for r in runs)
    assert record(f"G-C1[{config}]", ok, len(runs), 5, runs=[r.run_id for r in runs])


@pytest.mark.plumbing
@pytest.mark.parametrize("config", CONFIGS)
def test_gc2_integrity(lab: Lab, config: str) -> None:
    runs = [lab.run(config, t, "g1s0", "scripted_gullible", s) for t, s in SCRIPTED_RUNS]
    ok = sum(not r.problems for r in runs)
    assert record(f"G-C2[{config}]", ok, len(runs), 5, runs=[r.run_id for r in runs])


@pytest.mark.plumbing
@pytest.mark.parametrize("config", CONFIGS)
def test_gc3_replay_identical(lab: Lab, config: str) -> None:
    runs = [lab.run(config, t, "g1s0", "scripted_gullible", s) for t, s in SCRIPTED_RUNS]
    ok = 0
    for r in runs:
        [rid] = replay(r.run_id, settings=lab.settings)
        ok += sig(lab, rid) == sig(lab, r.run_id)
    assert record(f"G-C3[{config}]", ok, len(runs), 5, runs=[r.run_id for r in runs])


@pytest.mark.plumbing
@pytest.mark.parametrize("config", CONFIGS)
def test_gc4_no_false_alarms(lab: Lab, config: str) -> None:
    runs = [lab.run(config, t, None, "scripted_gullible", s) for t, s in SCRIPTED_RUNS]
    ok = sum(not lab.alerts(r) and not lab.verdicts(r) for r in runs)
    assert record(f"G-C4[{config}]", ok, len(runs), 5, runs=[r.run_id for r in runs])


@pytest.mark.model
def test_gc4_no_false_alarms_dev_open(lab: Lab) -> None:
    runs = [lab.run("s1_chain", t, None, "dev_open", s) for t, s in SCRIPTED_RUNS]
    ok = sum(not lab.alerts(r) and not lab.verdicts(r) for r in runs)
    notes = "; ".join(
        f"{r.run_id}: {[a.detector for a in lab.alerts(r)]}" for r in runs if lab.alerts(r)
    )
    assert record("G-C4[dev_open s1_chain]", ok, len(runs), 5, notes, runs=[r.run_id for r in runs])


@pytest.mark.plumbing
@pytest.mark.parametrize("config", CONFIGS)
def test_gc5_no_direct_network(lab: Lab, config: str, no_network: NetworkGuard) -> None:
    """Fresh runs under the guard: nothing tries to connect, nothing crashes."""
    ok = 0
    ids = []
    for t, s in SCRIPTED_RUNS:
        r = lab.run(config, t, "g1s0", "scripted_gullible", s + 100)
        ids.append(r.run_id)
        ok += r.status != "crashed"
    ok = ok if not no_network.blocked else 0
    assert record(f"G-C5[{config}]", ok, len(ids), 5, f"blocked={no_network.blocked}", ids)
