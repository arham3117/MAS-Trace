"""Symptom oracle: the symptom event of a successful attack (plan.md §7.10, P6.3).

Evaluation side. The tracer receives only the symptom event ID and a `symptom_check`
callable, never the attack details.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from mastrace.control.attacks import load_attack, marker_of
from mastrace.core.schemas import GroundTruth
from mastrace.environment.materializer import canary_for
from mastrace.environment.tasks import load_task
from mastrace.groundtruth.resolver import find_symptom
from mastrace.provenance.event_graph import EventGraph
from mastrace.provenance.payload_store import PayloadStore
from mastrace.runtime.run import read_manifest
from mastrace.settings import Settings, get_settings


def symptom_event(
    run_dir: Path, gt: GroundTruth | None, settings: Settings | None = None
) -> str | None:
    """G1: the leaking `send_email`; G2: the `final_output`; None for clean or failed runs."""
    if gt is None or gt.kind != "attack":
        return None
    settings = settings or get_settings()
    manifest = read_manifest(run_dir)
    task = load_task(manifest.task_id, settings.templates_dir)
    marker = marker_of(load_attack(gt.attack_id, allow_disabled=True)) if gt.goal == "G2" else None
    return find_symptom(
        EventGraph.from_run(run_dir),
        PayloadStore(run_dir / "payloads"),
        gt.goal,
        canary_for(manifest.seed),
        task.allowed_recipients,
        marker,
    )


def make_symptom_check(gt: GroundTruth, settings: Settings | None = None) -> Callable[[str], bool]:
    """A callable `symptom_check(run_id) -> bool` for replays of the attacked run."""
    settings = settings or get_settings()

    def check(run_id: str) -> bool:
        return symptom_event(settings.runs_dir / run_id, gt, settings) is not None

    return check
