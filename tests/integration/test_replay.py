"""P7.1: replay engine (gate check G-C3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mastrace.analysis.replay import replay
from mastrace.control.controller import run_with_attack
from mastrace.core.schemas import EventKind, ToolOutputOverride
from mastrace.evaluation.symptom_oracle import make_symptom_check
from mastrace.groundtruth.store import GroundTruthStore
from mastrace.provenance.event_store import EventStore
from mastrace.runtime.run import read_manifest
from mastrace.settings import Settings

Sig = list[tuple[str, str, str | None, str | None, str | None]]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def sig(settings: Settings, run_id: str) -> Sig:
    with EventStore.for_run(settings.runs_dir / run_id, readonly=True) as s:
        return [(e.kind.value, e.actor, e.turn_id, e.input_ref, e.output_ref) for e in s.iter()]


@pytest.mark.parametrize("config", ["s1_chain", "s2_two_way_mesh", "s3_mixed_two_paths"])
def test_replay_without_overrides_is_identical(settings: Settings, config: str) -> None:
    r = run_with_attack(config, "t02", "g1s0", "scripted_gullible", 1, settings=settings)
    [rid] = replay(r.run_id, settings=settings)
    assert rid == f"{r.run_id}__r1"
    assert sig(settings, rid) == sig(settings, r.run_id)
    m = read_manifest(settings.runs_dir / rid)
    assert m.replay_of == r.run_id and m.mode == "replay"
    with EventStore.for_run(settings.runs_dir / rid, readonly=True) as s:
        assert all(e.meta.get("cache_hit") for e in s.iter(EventKind.MODEL_CALL))


def test_neutralizing_entry_removes_symptom(settings: Settings) -> None:
    r = run_with_attack("s1_chain", "t01", "g1s0", "scripted_gullible", 1, settings=settings)
    o = ToolOutputOverride(agent="A", turn=1, call_index=0, replacement="[content unavailable]")
    [rid] = replay(r.run_id, [o], settings=settings)
    orig, new = sig(settings, r.run_id), sig(settings, rid)
    # everything up to and including A's first model call is identical
    first_read = next(i for i, e in enumerate(orig) if e[0] == "external_read")
    assert new[:first_read] == orig[:first_read]
    assert new[first_read][4] != orig[first_read][4]
    with GroundTruthStore(settings.ground_truth_path) as s:
        gt = s.get(r.run_id)
    assert gt is not None
    check = make_symptom_check(gt, settings)
    assert check(r.run_id) is True and check(rid) is False


def test_replays_are_numbered(settings: Settings) -> None:
    r = run_with_attack("s1_chain", "t01", None, "scripted_gullible", 1, settings=settings)
    assert replay(r.run_id, settings=settings, n=2) == [f"{r.run_id}__r1", f"{r.run_id}__r2"]
    assert replay(r.run_id, settings=settings) == [f"{r.run_id}__r3"]


def test_policy_overrides_survive_replay(settings: Settings) -> None:
    r = run_with_attack(
        "s3_mixed_two_paths",
        "t01",
        "g1s0",
        "scripted_gullible",
        1,
        settings=settings,
        policy_overrides={"C": "resistant"},
    )
    [rid] = replay(r.run_id, settings=settings)
    assert sig(settings, rid) == sig(settings, r.run_id)
    assert read_manifest(settings.runs_dir / rid).policy_overrides == {"C": "resistant"}
