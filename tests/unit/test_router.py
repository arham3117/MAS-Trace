"""P3.2: router checks, limits, ordering and termination."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from mastrace.core.schemas import DropMessageOverride, EventKind, GraphConfig
from mastrace.mediation.budget import TokenBudget
from mastrace.mediation.router import OutgoingMessage, Router
from mastrace.provenance.event_store import EventStore
from mastrace.provenance.payload_store import PayloadStore
from mastrace.provenance.recorder import EventDraft, Recorder
from mastrace.provenance.signer import Signer
from mastrace.runtime.graph_config import load_graph


def make(
    tmp_path: Path, cfg: GraphConfig, budget: int = 1000, **kw: object
) -> tuple[Router, Recorder]:
    rec = Recorder(
        run_id="r",
        stage=cfg.stage,
        store=EventStore.for_run(tmp_path / "run"),
        payloads=PayloadStore(tmp_path / "run" / "payloads"),
        signer=Signer(tmp_path / "keys"),
        code_version="x",
        clock=lambda: "t",
    )
    # a parent event for built_from
    rec.record_now(EventDraft(kind=EventKind.RUN_START, actor="controller", superstep=0))
    return Router(cfg, rec, TokenBudget(budget), **kw), rec  # type: ignore[arg-type]


def msg(s: str, t: str, order: int = 0, content: str = "hi") -> OutgoingMessage:
    return OutgoingMessage(sender=s, to=t, content=content, built_from="r:000001", order=order)


def reasons(router: Router, rec: Recorder) -> list[str | None]:
    return [
        e.meta.get("reason") if e.kind == EventKind.ROUTER_REJECT else "ok"
        for e in rec.store.iter()
        if e.kind in (EventKind.MESSAGE, EventKind.ROUTER_REJECT)
    ]


def test_accepted_message_recorded_and_delivered(tmp_path: Path) -> None:
    router, rec = make(tmp_path, load_graph("s1_chain"))
    [ev] = router.deliver([msg("A", "B", content="FACT: x")], superstep=1)
    assert ev.kind == EventKind.MESSAGE and ev.actor == "agent:A" and ev.receivers == ["B"]
    assert ev.link == {"from": "A", "to": "B", "type": "one_way", "count": 1}
    assert ev.built_from == ["r:000001"]
    assert rec.payloads.get(ev.output_ref or "") == "FACT: x"
    [item] = router.take_inbox("B")
    assert (item.event_id, item.sender, item.content) == (ev.event_id, "A", "FACT: x")
    assert not router.has_pending()


def test_reject_no_link(tmp_path: Path) -> None:
    router, rec = make(tmp_path, load_graph("s1_chain"))
    router.deliver([msg("B", "A"), msg("A", "C"), msg("A", "Z")], superstep=1)
    assert reasons(router, rec) == ["no_link", "no_link", "no_link"]
    assert not router.has_pending()


def test_reject_limit_per_direction_two_way(tmp_path: Path) -> None:
    router, rec = make(tmp_path, load_graph("s2_two_way_chain"))
    router.deliver([msg("A", "B", i) for i in range(4)], superstep=1)
    router.deliver([msg("B", "A", i) for i in range(3)], superstep=2)
    router.deliver([msg("A", "B"), msg("B", "A")], superstep=3)
    assert reasons(router, rec) == ["ok"] * 3 + ["limit"] + ["ok"] * 3 + ["limit", "limit"]
    assert router.accepted == {("A", "B"): 3, ("B", "A"): 3}


def test_reject_budget(tmp_path: Path) -> None:
    router, rec = make(tmp_path, load_graph("s1_chain"), budget=10)
    router.budget.used = 11
    router.deliver([msg("A", "B")], superstep=1)
    assert reasons(router, rec) == ["budget"]


def test_reject_quarantined(tmp_path: Path) -> None:
    router, rec = make(tmp_path, load_graph("s1_chain"))
    q = router.quarantine("B", superstep=1, symptom_event_id="r:000001", verdict_id="v1")
    assert q.kind == EventKind.QUARANTINE and q.meta["verdict_id"] == "v1"
    router.deliver([msg("A", "B"), msg("B", "C")], superstep=1)
    assert reasons(router, rec) == ["quarantined", "quarantined"]


def test_drop_message_override(tmp_path: Path) -> None:
    drop = DropMessageOverride.model_validate({"from": "A", "to": "B", "nth": 2})
    router, rec = make(tmp_path, load_graph("s1_chain"), overrides=[drop])
    router.deliver([msg("A", "B", 0), msg("A", "B", 1), msg("A", "B", 2)], superstep=1)
    assert reasons(router, rec) == ["ok", "dropped", "ok"]


def test_deterministic_order_under_shuffle(tmp_path: Path) -> None:
    cfg = load_graph("s2_two_way_mesh")
    batch = [
        msg("A", "B", 0),
        msg("A", "C", 1),
        msg("B", "C", 0),
        msg("C", "A", 0),
        msg("C", "B", 1),
        msg("C", "D", 2),
        msg("D", "E", 0),
        msg("D", "C", 1),
    ]
    seqs = []
    for i in range(5):
        router, rec = make(tmp_path / str(i), cfg)
        shuffled = batch[:]
        random.Random(i).shuffle(shuffled)
        router.deliver(shuffled, superstep=1)
        seqs.append(
            [(e.actor, e.receivers[0]) for e in rec.store.iter() if e.kind == EventKind.MESSAGE]
        )
    assert all(s == seqs[0] for s in seqs)
    assert [r for _, r in seqs[0]] == sorted(r for _, r in seqs[0])


@pytest.mark.parametrize(
    ("superstep", "sink_out", "pending", "over_budget", "expected"),
    [
        (3, True, False, False, "completed"),
        (3, True, True, False, None),
        (3, False, True, True, "stopped_budget"),
        (20, False, True, False, "stopped_superstep_limit"),
        (3, False, False, False, "stopped_idle"),
        (3, False, True, False, None),
    ],
)
def test_termination(
    tmp_path: Path,
    superstep: int,
    sink_out: bool,
    pending: bool,
    over_budget: bool,
    expected: str | None,
) -> None:
    router, _ = make(tmp_path, load_graph("s1_chain"), budget=10)
    if pending:
        router.put_task("A", "r:000001", "task")
    if over_budget:
        router.budget.used = 11
    assert router.decide(superstep, sink_out) == expected


def test_stats_count_every_message(tmp_path: Path) -> None:
    router, rec = make(tmp_path, load_graph("s1_chain"))
    router.deliver([msg("A", "B"), msg("B", "A")], superstep=1)
    n_events = sum(e.kind in (EventKind.MESSAGE, EventKind.ROUTER_REJECT) for e in rec.store.iter())
    assert router.stats() == {"messages": 2} and n_events == 2
