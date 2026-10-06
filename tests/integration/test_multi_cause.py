"""P11.2: two poisoned pages, read by A and by B, are both confirmed as entry events."""

from __future__ import annotations

from pathlib import Path

from mastrace.analysis.tracer import Tracer
from mastrace.control.attacks import load_attack
from mastrace.control.injector import inject
from mastrace.core.canonical import sha256_hex
from mastrace.core.schemas import TaskSpec
from mastrace.evaluation.symptom_oracle import make_symptom_check, symptom_event
from mastrace.groundtruth.store import GroundTruthStore
from mastrace.provenance.event_store import EventStore
from mastrace.runtime.run import run_once
from mastrace.settings import Settings


def test_double_injection_confirms_both(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    spec = load_attack("g1s0")
    poisoned: list[str] = []

    def double(env: Path, task: TaskSpec, run_id: str) -> None:
        for agent, url in [("A", task.sources[0]), ("B", task.sources_2[0])]:
            inject(env, task, spec, run_id, settings.ground_truth_path, agent, url)
            page = env / "web" / url.split("/")[2] / (url.split("/", 3)[3] + ".md")
            poisoned.append("sha256:" + sha256_hex(page.read_text()))

    r = run_once(
        "s1_fanin", "t01", "g1s0", "scripted_gullible", 1, settings=settings, inject=double
    )
    with GroundTruthStore(settings.ground_truth_path) as s:
        gt = s.get(r.run_id)  # the last injection's row (B); the symptom check is goal-based
    assert gt is not None
    sid = symptom_event(r.run_dir, gt, settings)
    assert sid is not None
    v = Tracer(settings).trace(r.run_id, sid, make_symptom_check(gt, settings))
    assert v.status == "confirmed"
    with EventStore.for_run(r.run_dir, readonly=True) as es:
        refs = {es.get(e).output_ref for e in v.confirmed_entry_events}
        agents = {es.get(e).actor for e in v.confirmed_entry_events}
    assert refs == set(poisoned) and agents == {"agent:A", "agent:B"}
    singles = {x["candidate"]: x["confirmed"] for x in v.replays if x["kind"] == "candidate"}
    assert not any(singles[e] for e in v.confirmed_entry_events)  # neither alone suffices
    assert any(x["kind"] == "candidate_set" and x["confirmed"] for x in v.replays)
