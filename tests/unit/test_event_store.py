"""P1.5: EventStore."""

from __future__ import annotations

import inspect
import re
import sqlite3
from pathlib import Path

import pytest

from mastrace.core.errors import EventNotFound, OutOfOrderAppend
from mastrace.core.schemas import Alert, EventKind, EventRecord, Verdict
from mastrace.provenance import event_store
from mastrace.provenance.event_store import EventStore


def ev(seq: int, kind: EventKind = EventKind.MESSAGE, actor: str = "router") -> EventRecord:
    return EventRecord(
        event_id=f"r:{seq:06d}",
        run_id="r",
        seq=seq,
        stage=1,
        code_version="x",
        time="t",
        superstep=0,
        kind=kind,
        actor=actor,
        prev_hash="p",
        record_hash="h",
        signature="s",
    )


@pytest.fixture
def store(tmp_path: Path) -> EventStore:
    return EventStore.for_run(tmp_path)


def test_append_get_iter(store: EventStore) -> None:
    store.append(ev(1, EventKind.RUN_START, "controller"))
    store.append(ev(2))
    store.append(ev(3, EventKind.MODEL_CALL, "agent:A"))
    assert store.count() == 3
    assert store.get("r:000002") == ev(2)
    assert [e.seq for e in store.iter()] == [1, 2, 3]
    assert [e.seq for e in store.iter(EventKind.MESSAGE)] == [2]
    last = store.last()
    assert last is not None and last.seq == 3


def test_empty_store(store: EventStore) -> None:
    assert store.count() == 0
    assert store.last() is None
    with pytest.raises(EventNotFound):
        store.get("r:000001")


def test_append_out_of_order_raises(store: EventStore) -> None:
    store.append(ev(1))
    with pytest.raises(OutOfOrderAppend):
        store.append(ev(3))
    with pytest.raises(OutOfOrderAppend):
        store.append(ev(1))
    with pytest.raises(OutOfOrderAppend):
        EventStore(store.path).append_many([ev(2), ev(4)])
    assert store.count() == 1  # the failed batch was rolled back


def test_first_seq_must_be_one(store: EventStore) -> None:
    with pytest.raises(OutOfOrderAppend):
        store.append(ev(2))


def test_no_update_or_delete_path_in_source() -> None:
    src = inspect.getsource(event_store)
    forbidden = re.compile(
        r"(UPDATE\s+events\b|DELETE\s+FROM\s+events\b|REPLACE\s+INTO\s+events\b|"
        r"INSERT\s+OR\s+REPLACE\s+INTO\s+events\b|DROP\s+TABLE\s+events\b)",
        re.IGNORECASE,
    )
    assert not forbidden.search(src)
    public = {n for n in vars(EventStore) if not n.startswith("_")}
    assert not {n for n in public if re.search(r"update|delete|remove|edit", n)}


def test_triggers_block_raw_update_and_delete(store: EventStore) -> None:
    store.append(ev(1))
    store.close()
    conn = sqlite3.connect(store.path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE events SET actor = 'x'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("DELETE FROM events")
    conn.close()


def test_wal_and_indexes(store: EventStore) -> None:
    conn = sqlite3.connect(store.path)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    idx = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"idx_events_kind", "idx_events_actor", "idx_events_turn", "idx_events_seq"} <= idx
    conn.close()


def test_alerts_verdicts_summary(store: EventStore) -> None:
    a = Alert(detector="canary_leak", severity="high", event_id="r:000002", details={"k": 1})
    store.add_alert(a)
    assert store.alerts() == [a]
    v = Verdict(
        verdict_id="v1", run_id="r", method="tracer_v1", symptom_event_id="e", status="confirmed"
    )
    store.add_verdict(v)
    assert store.verdicts() == [v]
    assert store.summary() is None
    store.set_summary({"status": "running"})
    store.set_summary({"status": "completed"})
    assert store.summary() == {"status": "completed"}


def test_readonly_store(store: EventStore) -> None:
    store.append(ev(1))
    ro = EventStore(store.path, readonly=True)
    assert ro.count() == 1
    with pytest.raises(sqlite3.OperationalError):
        ro.append(ev(2))
    ro.close()
