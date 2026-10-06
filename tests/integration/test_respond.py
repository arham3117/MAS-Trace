"""P12.2: quarantine (containment) and healing, on scripted g1s0 runs across all stages."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastrace.analysis.respond import respond
from mastrace.analysis.tracer import Tracer
from mastrace.control.controller import run_with_attack
from mastrace.core.schemas import EventKind
from mastrace.evaluation.symptom_oracle import make_symptom_check, symptom_event
from mastrace.groundtruth.store import GroundTruthStore
from mastrace.provenance.event_store import EventStore
from mastrace.settings import Settings

CONFIGS = [
    "s1_chain",
    "s1_fanin",
    "s1_fanout",
    "s2_two_way_chain",
    "s2_two_way_mesh",
    "s3_mixed_two_paths",
    "s3_whiteboard",
]


@pytest.mark.parametrize("config", CONFIGS)
def test_contain_and_heal(tmp_path: Path, config: str) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    r = run_with_attack(config, "t01", "g1s0", "scripted_gullible", 1, settings=settings)
    with GroundTruthStore(settings.ground_truth_path) as s:
        gt = s.get(r.run_id)
    assert gt is not None
    sid = symptom_event(r.run_dir, gt, settings)
    assert sid is not None
    v = Tracer(settings).trace(r.run_id, sid, make_symptom_check(gt, settings))
    rec = respond(r.run_id, v, settings)

    assert rec.contained and rec.recovered and rec.alerts_after == []
    assert rec.utility_after >= 2 / 3
    assert rec.extra_tokens > 0
    # the router recorded the quarantine and rejected the poisoned turn's messages
    with EventStore.for_run(settings.runs_dir / rec.containment_run, readonly=True) as s:
        q = list(s.iter(EventKind.QUARANTINE))
        rejected = [
            e for e in s.iter(EventKind.ROUTER_REJECT) if e.meta.get("reason") == "quarantined"
        ]
        denied = [e for e in s.iter() if e.meta.get("quarantined")]
    assert len(q) == 1 and q[0].meta["turn"] == 1 and q[0].meta["agent"] == "A"
    assert rejected or denied
    line = json.loads((r.run_dir / "heal.jsonl").read_text().splitlines()[-1])
    assert line["recovered"] is True and line["verdict_id"] == v.verdict_id


def test_respond_needs_confirmed_verdict(tmp_path: Path) -> None:
    from mastrace.core.schemas import Verdict

    v = Verdict(verdict_id="v", run_id="r", method="m", symptom_event_id="s", status="unconfirmed")
    with pytest.raises(ValueError, match="confirmed"):
        respond("r", v, Settings(data_dir=tmp_path))
