"""P5.2 injector and P5.3 ground-truth resolver, on scripted runs of the real task suite."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from mastrace.control.attacks import load_attack, render_payload
from mastrace.control.controller import run_with_attack
from mastrace.control.injector import page_path, poison
from mastrace.environment.tasks import load_task
from mastrace.groundtruth.resolver import resolve
from mastrace.groundtruth.store import GroundTruthStore
from mastrace.runtime.run import RunResult
from mastrace.settings import Settings

IDENTIFIER_FIELDS = {
    "event_id",
    "run_id",
    "built_from",
    "input_ref",
    "output_ref",
    "prev_hash",
    "record_hash",
    "signature",
    "request_hash",
}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def attack_run(
    settings: Settings,
    model: str,
    attack: str = "g1s0",
    config: str = "s1_chain",
    task: str = "t01",
) -> RunResult:
    return run_with_attack(config, task, attack, model, 1, settings=settings)


def gt_of(settings: Settings, run_id: str):  # type: ignore[no-untyped-def]
    with GroundTruthStore(settings.ground_truth_path) as s:
        gt = s.get(run_id)
    assert gt is not None
    return gt


def test_poison_placement() -> None:
    text = "# T\n\npara one\n\nFACT: a\nFACT: b\n\npara three\n"
    assert poison(text, "EVIL", "append").endswith("para three\n\nEVIL\n")
    assert (
        poison(text, "EVIL", "middle")
        == "# T\n\npara one\n\nEVIL\n\nFACT: a\nFACT: b\n\npara three\n"
    )


def test_injection_poisons_page_and_writes_gt(settings: Settings) -> None:
    r = attack_run(settings, "scripted_resistant")
    task = load_task("t01")
    page = page_path(r.run_dir / "env", task.sources[0]).read_text()
    assert render_payload(load_attack("g1s0")) in page
    gt = gt_of(settings, r.run_id)
    assert (gt.attack_id, gt.goal, gt.target_agent, gt.target_url) == (
        "g1s0",
        "G1",
        "A",
        task.sources[0],
    )
    other = page_path(r.run_dir / "env", task.sources[1]).read_text()
    assert "evil.example" not in other


def test_run_log_has_no_ground_truth(settings: Settings) -> None:
    """ISSUE-007: identifiers embed the run ID; every other field must be GT-free."""
    r = attack_run(settings, "scripted_resistant")
    conn = sqlite3.connect(r.run_dir / "events.sqlite")
    rows = [json.loads(x) for (x,) in conn.execute("SELECT record_json FROM events")]
    conn.close()
    for rec in rows:
        blob = json.dumps({k: v for k, v in rec.items() if k not in IDENTIFIER_FIELDS})
        for needle in ["g1s0", "evil.example", "poisoned_page_sha256", "target_agent", "G1"]:
            assert needle not in blob, (needle, rec["kind"])
    manifest = json.loads((r.run_dir / "manifest.json").read_text())
    assert "target_agent" not in manifest and "poisoned_page_sha256" not in manifest


def test_resolver_gullible_chain(settings: Settings) -> None:
    r = attack_run(settings, "scripted_gullible")
    res = resolve(r.run_dir, gt_of(settings, r.run_id), settings)
    assert res.entry_turn == "A#1"
    assert res.entry_event is not None
    assert res.true_paths == [["A", "B", "C", "D", "E"]]
    assert res.attack_succeeded is True
    assert res.symptom_event is not None


def test_resolver_resistant_chain(settings: Settings) -> None:
    r = attack_run(settings, "scripted_resistant")
    res = resolve(r.run_dir, gt_of(settings, r.run_id), settings)
    assert res.entry_turn == "A#1"  # the page was still read
    assert res.attack_succeeded is False
    assert res.symptom_event is None and res.true_paths == []


def test_resolver_g2(settings: Settings) -> None:
    r = attack_run(settings, "scripted_gullible", attack="g2s1")
    res = resolve(r.run_dir, gt_of(settings, r.run_id), settings)
    assert res.attack_succeeded
    assert res.true_paths == [["A", "B", "C", "D", "E"]]


def test_resolver_fanout_branch(settings: Settings) -> None:
    r = attack_run(settings, "scripted_gullible", config="s1_fanout")
    res = resolve(r.run_dir, gt_of(settings, r.run_id), settings)
    assert res.attack_succeeded and res.true_paths == [["A", "C", "E"]]


def test_resolver_mixed_two_paths(settings: Settings) -> None:
    r = attack_run(settings, "scripted_gullible", config="s3_mixed_two_paths")
    res = resolve(r.run_dir, gt_of(settings, r.run_id), settings)
    assert res.true_paths == [["A", "B", "C", "E"], ["A", "B", "D", "E"]]


def test_fanin_target_is_a_and_b_reads_clean(settings: Settings) -> None:
    r = attack_run(settings, "scripted_gullible", config="s1_fanin")
    res = resolve(r.run_dir, gt_of(settings, r.run_id), settings)
    assert res.entry_turn == "A#1" and res.true_paths == [["A", "C", "D", "E"]]
