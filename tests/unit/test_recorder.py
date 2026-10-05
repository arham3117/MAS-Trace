"""P1.6: Recorder and EventBuffer."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from mastrace.core.errors import MastraceError, UnknownLocalRef
from mastrace.core.schemas import EventKind, EventRecord
from mastrace.provenance.event_store import EventStore
from mastrace.provenance.payload_store import PayloadStore
from mastrace.provenance.recorder import (
    GENESIS,
    EventBuffer,
    EventDraft,
    Recorder,
    compute_record_hash,
)
from mastrace.provenance.signer import Signer, verify


def make_recorder(root: Path, keys: Path) -> Recorder:
    return Recorder(
        run_id="run1",
        stage=1,
        store=EventStore.for_run(root),
        payloads=PayloadStore(root / "payloads"),
        signer=Signer(keys),
        code_version="abc1234",
        clock=lambda: "2026-10-05T00:00:00Z",
    )


def turn_buffer(agent: str, superstep: int = 1) -> EventBuffer:
    buf = EventBuffer(agent_id=agent, turn_id=f"{agent}#1", superstep=superstep)
    m0 = buf.add(
        EventKind.MODEL_CALL,
        call_index=0,
        built_from=["run1:000001"],
        input_text=f"prompt {agent}",
        output_text='{"action":"tool"}',
    )
    t0 = buf.add(
        EventKind.EXTERNAL_READ,
        call_index=0,
        built_from=[m0],
        input_text='{"url":"u"}',
        output_text=f"page {agent}",
        meta={"tool": "web_fetch"},
    )
    buf.add(
        EventKind.MODEL_CALL,
        call_index=1,
        built_from=["run1:000001", m0, t0],
        input_text=f"prompt2 {agent}",
        output_text='{"action":"respond"}',
    )
    return buf


def start(rec: Recorder) -> EventRecord:
    return rec.record_now(
        EventDraft(kind=EventKind.TASK_INPUT, actor="user", superstep=0, output_text="task")
    )


def test_commit_assigns_ids_and_resolves_local_refs(tmp_path: Path) -> None:
    rec = make_recorder(tmp_path / "run", tmp_path / "keys")
    first = start(rec)
    assert first.event_id == "run1:000001" and first.prev_hash == GENESIS
    res = rec.commit([turn_buffer("B"), turn_buffer("A")])
    ids = [r.event_id for r in res.records]
    assert ids == [f"run1:{i:06d}" for i in range(2, 8)]
    assert [r.turn_id for r in res.records] == ["A#1"] * 3 + ["B#1"] * 3
    a_m0, a_t0, a_m1 = res.records[:3]
    assert a_t0.built_from == [a_m0.event_id]
    assert a_m1.built_from == ["run1:000001", a_m0.event_id, a_t0.event_id]
    assert a_m0.actor == "agent:A"
    assert res.id_map["local:A#1:2"] == a_m1.event_id
    # later events can still point at local refs from an earlier commit
    msg = rec.record_now(
        EventDraft(
            kind=EventKind.MESSAGE,
            actor="router",
            superstep=1,
            built_from=["local:A#1:2"],
            receivers=["B"],
            output_text="hi",
        )
    )
    assert msg.built_from == [a_m1.event_id]


def test_hash_chain_and_signatures(tmp_path: Path) -> None:
    rec = make_recorder(tmp_path / "run", tmp_path / "keys")
    start(rec)
    rec.commit([turn_buffer("A")])
    prev = GENESIS
    for r in rec.store.iter():
        assert r.prev_hash == prev
        assert r.record_hash == compute_record_hash(r.hashable_dict())
        assert verify(r.record_hash, r.signature, rec.signer.public_key)
        prev = r.record_hash


def test_payloads_stored(tmp_path: Path) -> None:
    rec = make_recorder(tmp_path / "run", tmp_path / "keys")
    res = rec.commit([turn_buffer("A")])
    r = res.records[1]
    assert r.output_ref is not None and rec.payloads.get(r.output_ref) == "page A"


def test_commit_order_independent_of_arrival(tmp_path: Path) -> None:
    keys = tmp_path / "keys"
    r1 = make_recorder(tmp_path / "r1", keys)
    r2 = make_recorder(tmp_path / "r2", keys)
    for r in (r1, r2):
        start(r)
    r1.commit([turn_buffer(a) for a in ["A", "B", "C", "D", "E"]])
    r2.commit([turn_buffer(a) for a in ["E", "C", "A", "D", "B"]])
    assert list(r1.store.iter()) == list(r2.store.iter())


def test_unknown_local_ref(tmp_path: Path) -> None:
    rec = make_recorder(tmp_path / "run", tmp_path / "keys")
    with pytest.raises(UnknownLocalRef):
        rec.record_now(
            EventDraft(
                kind=EventKind.MESSAGE, actor="router", superstep=1, built_from=["local:Z#1:0"]
            )
        )
    assert rec.store.count() == 0
    assert start(rec).seq == 1  # state rolled back after the failure


def test_duplicate_turn_buffers_rejected(tmp_path: Path) -> None:
    rec = make_recorder(tmp_path / "run", tmp_path / "keys")
    with pytest.raises(MastraceError, match="duplicate"):
        rec.commit([turn_buffer("A"), turn_buffer("A")])


def test_recorder_resumes_chain_from_store(tmp_path: Path) -> None:
    rec = make_recorder(tmp_path / "run", tmp_path / "keys")
    first = start(rec)
    rec.store.close()
    rec2 = make_recorder(tmp_path / "run", tmp_path / "keys")
    second = start(rec2)
    assert second.seq == 2 and second.prev_hash == first.record_hash


def test_commit_1000_events_under_2s(tmp_path: Path) -> None:
    rec = make_recorder(tmp_path / "run", tmp_path / "keys")
    buffers = []
    for i in range(200):
        buf = EventBuffer(
            agent_id="ABCDE"[i % 5], turn_id=f"{'ABCDE'[i % 5]}#{i // 5 + 1}", superstep=1
        )
        for k in range(5):
            buf.add(
                EventKind.MODEL_CALL,
                call_index=k,
                input_text=f"in {i} {k}",
                output_text=f"out {i} {k}",
            )
        buffers.append(buf)
    t0 = time.perf_counter()
    rec.commit(buffers)
    elapsed = time.perf_counter() - t0
    assert rec.store.count() == 1000
    assert elapsed < 2.0, f"1000 events took {elapsed:.2f}s"
