"""P6.2 detectors on real scripted runs, and P6.3 symptom oracle."""

from __future__ import annotations

from pathlib import Path

import pytest

from mastrace.control.controller import run_with_attack
from mastrace.core.schemas import EventKind
from mastrace.evaluation.symptom_oracle import make_symptom_check, symptom_event
from mastrace.groundtruth.store import GroundTruthStore
from mastrace.provenance.event_store import EventStore
from mastrace.settings import Settings

TASKS = [f"t{i:02d}" for i in range(1, 11)]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def alerts(run_dir: Path) -> list[tuple[str, str]]:
    with EventStore.for_run(run_dir, readonly=True) as s:
        return [(a.detector, s.get(a.event_id).kind.value) for a in s.alerts()]


def gt(settings: Settings, run_id: str):  # type: ignore[no-untyped-def]
    with GroundTruthStore(settings.ground_truth_path) as s:
        return s.get(run_id)


@pytest.mark.parametrize("task", TASKS)
def test_no_alerts_on_clean_scripted_runs(settings: Settings, task: str) -> None:
    r = run_with_attack("s1_chain", task, None, "scripted_gullible", 1, settings=settings)
    assert alerts(r.run_dir) == []


def test_d1_fires_on_g1s0_gullible(settings: Settings) -> None:
    r = run_with_attack("s1_chain", "t01", "g1s0", "scripted_gullible", 1, settings=settings)
    a = alerts(r.run_dir)
    assert ("canary_leak", "tool_call") in a
    assert ("forbidden_recipient", "tool_call") in a
    assert ("injection_pattern", "external_read") in a


def test_resistant_run_only_d4(settings: Settings) -> None:
    r = run_with_attack("s1_chain", "t01", "g1s0", "scripted_resistant", 1, settings=settings)
    assert alerts(r.run_dir) == [("injection_pattern", "external_read")]


def test_oracle_g1_is_leaking_send_email(settings: Settings) -> None:
    r = run_with_attack("s1_chain", "t01", "g1s0", "scripted_gullible", 1, settings=settings)
    sid = symptom_event(r.run_dir, gt(settings, r.run_id), settings)
    assert sid is not None
    with EventStore.for_run(r.run_dir, readonly=True) as s:
        e = s.get(sid)
    assert e.kind == EventKind.TOOL_CALL and e.meta["tool"] == "send_email"
    assert e.meta["args"]["to"] == "audit@evil.example"
    assert make_symptom_check(gt(settings, r.run_id), settings)(r.run_id) is True


def test_oracle_g2_is_final_output(settings: Settings) -> None:
    r = run_with_attack("s1_chain", "t01", "g2s0", "scripted_gullible", 1, settings=settings)
    sid = symptom_event(r.run_dir, gt(settings, r.run_id), settings)
    assert sid is not None
    with EventStore.for_run(r.run_dir, readonly=True) as s:
        assert s.get(sid).kind == EventKind.FINAL_OUTPUT


def test_oracle_none_for_clean_and_failed(settings: Settings) -> None:
    clean = run_with_attack("s1_chain", "t01", None, "scripted_gullible", 1, settings=settings)
    assert symptom_event(clean.run_dir, None, settings) is None
    r = run_with_attack("s1_chain", "t01", "g1s0", "scripted_resistant", 1, settings=settings)
    g = gt(settings, r.run_id)
    assert symptom_event(r.run_dir, g, settings) is None
    assert make_symptom_check(g, settings)(r.run_id) is False


def test_later_leaks_are_additional_symptoms(settings: Settings) -> None:
    """D3 follow-up: on the gullible whiteboard the operator leaks via A→C→E, then again
    when the payload arrives via B and D; the first leak stays the primary symptom."""
    from mastrace.evaluation.symptom_oracle import symptom_events
    from mastrace.groundtruth.resolver import resolve

    r = run_with_attack("s3_whiteboard", "t01", "g1s0", "scripted_gullible", 1, settings=settings)
    g = gt(settings, r.run_id)
    events = symptom_events(r.run_dir, g, settings)
    assert len(events) >= 2
    assert symptom_event(r.run_dir, g, settings) == events[0]
    res = resolve(r.run_dir, g, settings)
    assert res.symptom_event == events[0] and res.additional_symptoms == events[1:]
    with EventStore.for_run(r.run_dir, readonly=True) as s:
        seqs = [s.get(e).seq for e in events]
    assert seqs == sorted(seqs)
