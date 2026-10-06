"""Respond: contain and heal after a confirmed verdict (plan.md P12.2).

Two replays of the attacked run (ISSUE-026 records why there are two):

1. **Containment.** The router quarantines the entry agent's poisoned turn: it records a
   `quarantine` event, rejects that turn's outgoing messages, and the tool gateway revokes
   that turn's tools. This shows the harm can be stopped where it entered.
2. **Healing.** The confirmed entry events are neutralized (`tool_output` overrides) and
   the run continues normally, so the team can still finish its task.

The heal record compares detectors (D1/D2) and utility before and after. Analysis side:
it uses the task spec (expected facts), never ground truth.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from mastrace.analysis.replay import replay
from mastrace.core.ids import parse_turn_id
from mastrace.core.schemas import QuarantineRequest, ToolOutputOverride, Verdict
from mastrace.environment.checkers import utility
from mastrace.environment.tasks import load_task
from mastrace.provenance.event_store import EventStore
from mastrace.runtime.run import read_manifest
from mastrace.settings import Settings, get_settings

HARM_DETECTORS = ("canary_leak", "forbidden_recipient")
NEUTRAL = "[content unavailable]"


@dataclass
class HealRecord:
    """Outcome of one respond() call."""

    run_id: str
    verdict_id: str
    entry_events: list[str]
    quarantined: dict[str, Any]
    containment_run: str
    healing_run: str
    contained: bool  # no D1/D2 alerts in the containment replay
    recovered: bool  # no D1/D2 alerts in the healing replay
    utility_before: float
    utility_contained: float
    utility_after: float
    extra_tokens: int
    alerts_after: list[str] = field(default_factory=list)


def _harm_alerts(settings: Settings, run_id: str) -> list[str]:
    with EventStore.for_run(settings.runs_dir / run_id, readonly=True) as s:
        return [a.detector for a in s.alerts() if a.detector in HARM_DETECTORS]


def _tokens(settings: Settings, run_id: str) -> int:
    with EventStore.for_run(settings.runs_dir / run_id, readonly=True) as s:
        return int((s.summary() or {}).get("tokens", 0))


def respond(run_id: str, verdict: Verdict, settings: Settings | None = None) -> HealRecord:
    """Quarantine the entry turn in one replay, heal in another, and record the outcome."""
    settings = settings or get_settings()
    if verdict.status != "confirmed" or not verdict.entry_turn:
        raise ValueError("respond() needs a confirmed verdict")
    run_dir = settings.runs_dir / run_id
    manifest = read_manifest(run_dir)
    task = load_task(manifest.task_id, settings.templates_dir)

    agent, turn = parse_turn_id(verdict.entry_turn)
    q = QuarantineRequest(
        agent=agent,
        turn=turn,
        verdict_id=verdict.verdict_id,
        symptom_event_id=verdict.symptom_event_id,
    )
    [contain_id] = replay(run_id, settings=settings, quarantine=[q])

    with EventStore.for_run(run_dir, readonly=True) as s:
        entries = [s.get(e) for e in verdict.confirmed_entry_events]
    overrides = []
    for e in entries:
        a, t = parse_turn_id(str(e.turn_id))
        overrides.append(
            ToolOutputOverride(
                agent=a, turn=t, call_index=int(e.call_index or 0), replacement=NEUTRAL
            )
        )
    [heal_id] = replay(run_id, overrides, settings=settings)

    def util(rid: str) -> float:
        return utility(settings.runs_dir / rid, task.expected_facts, task.match_any)

    after = _harm_alerts(settings, heal_id)
    rec = HealRecord(
        run_id=run_id,
        verdict_id=verdict.verdict_id,
        entry_events=list(verdict.confirmed_entry_events),
        quarantined=q.model_dump(mode="json"),
        containment_run=contain_id,
        healing_run=heal_id,
        contained=not _harm_alerts(settings, contain_id),
        recovered=not after,
        utility_before=util(run_id),
        utility_contained=util(contain_id),
        utility_after=util(heal_id),
        extra_tokens=_tokens(settings, contain_id) + _tokens(settings, heal_id),
        alerts_after=after,
    )
    path = run_dir / "heal.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(rec), sort_keys=True) + "\n")
    return rec
