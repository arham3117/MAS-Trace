"""P1.7: integrity verifier and `mastrace verify-log`."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mastrace.cli import app
from mastrace.core.canonical import canonical_json
from mastrace.core.schemas import EventKind
from mastrace.provenance.event_store import EventStore
from mastrace.provenance.payload_store import PayloadStore
from mastrace.provenance.recorder import EventBuffer, EventDraft, Recorder
from mastrace.provenance.signer import Signer
from mastrace.provenance.verifier import verify_run


def build_run(run_dir: Path, keys_dir: Path) -> Recorder:
    rec = Recorder(
        run_id="run1",
        stage=1,
        store=EventStore.for_run(run_dir),
        payloads=PayloadStore(run_dir / "payloads"),
        signer=Signer(keys_dir),
        code_version="abc",
    )
    rec.record_now(EventDraft(kind=EventKind.RUN_START, actor="controller", superstep=0))
    rec.record_now(
        EventDraft(kind=EventKind.TASK_INPUT, actor="user", superstep=0, output_text="task")
    )
    buf = EventBuffer(agent_id="A", turn_id="A#1", superstep=1)
    m0 = buf.add(EventKind.MODEL_CALL, call_index=0, input_text="p1", output_text="o1")
    t0 = buf.add(
        EventKind.EXTERNAL_READ, call_index=0, built_from=[m0], input_text="u", output_text="page"
    )
    buf.add(
        EventKind.MODEL_CALL, call_index=1, built_from=[m0, t0], input_text="p2", output_text="o2"
    )
    rec.commit([buf])
    rec.record_now(
        EventDraft(
            kind=EventKind.MESSAGE,
            actor="router",
            superstep=1,
            built_from=["local:A#1:2"],
            output_text="msg",
        )
    )
    rec.record_now(EventDraft(kind=EventKind.RUN_END, actor="controller", superstep=1))
    rec.store.close()
    return rec


@pytest.fixture
def run(tmp_path: Path) -> tuple[Path, Path]:
    run_dir, keys = tmp_path / "runs" / "run1", tmp_path / "keys"
    build_run(run_dir, keys)
    return run_dir, keys


def raw(run_dir: Path) -> sqlite3.Connection:
    """Open the DB as an attacker would: drop the append-only triggers first."""
    conn = sqlite3.connect(run_dir / "events.sqlite")
    conn.execute("DROP TRIGGER events_append_only_u")
    conn.execute("DROP TRIGGER events_append_only_d")
    return conn


def get_json(conn: sqlite3.Connection, seq: int) -> dict[str, Any]:
    row = conn.execute("SELECT record_json FROM events WHERE seq=?", (seq,)).fetchone()
    out: dict[str, Any] = json.loads(row[0])
    return out


def put_json(conn: sqlite3.Connection, seq: int, d: dict[str, Any]) -> None:
    conn.execute("UPDATE events SET record_json=? WHERE seq=?", (canonical_json(d), seq))
    conn.commit()


def checks(run_dir: Path, keys: Path) -> set[str]:
    return {p.check for p in verify_run(run_dir, keys_dir=keys)}


def test_clean_run_has_no_problems(run: tuple[Path, Path]) -> None:
    assert verify_run(run[0], keys_dir=run[1]) == []


def test_edited_field_detected(run: tuple[Path, Path]) -> None:
    conn = raw(run[0])
    d = get_json(conn, 4)
    d["actor"] = "agent:B"
    put_json(conn, 4, d)
    assert "record_hash" in checks(*run)


def test_edited_field_with_rehash_detected(run: tuple[Path, Path]) -> None:
    """Recomputing the record hash is not enough: the signature and the chain break."""
    from mastrace.provenance.recorder import compute_record_hash

    conn = raw(run[0])
    d = get_json(conn, 4)
    d["actor"] = "agent:B"
    d["record_hash"] = compute_record_hash(
        {k: v for k, v in d.items() if k not in ("record_hash", "signature")}
    )
    put_json(conn, 4, d)
    assert {"signature", "prev_hash"} <= checks(*run)


def test_deleted_record_detected(run: tuple[Path, Path]) -> None:
    conn = raw(run[0])
    conn.execute("DELETE FROM events WHERE seq=3")
    conn.commit()
    assert {"seq_gap", "prev_hash"} <= checks(*run)


def test_reordered_records_detected(run: tuple[Path, Path]) -> None:
    conn = raw(run[0])
    a, b = get_json(conn, 3), get_json(conn, 4)
    put_json(conn, 3, b)
    put_json(conn, 4, a)
    assert {"row_mismatch", "prev_hash"} <= checks(*run)


def test_altered_payload_detected(run: tuple[Path, Path]) -> None:
    ref = get_json(raw(run[0]), 4)["output_ref"]
    PayloadStore(run[0] / "payloads").path_for(ref).write_text("evil page")
    assert checks(*run) == {"payload_corrupt"}


def test_missing_payload_detected(run: tuple[Path, Path]) -> None:
    ref = get_json(raw(run[0]), 4)["output_ref"]
    PayloadStore(run[0] / "payloads").path_for(ref).unlink()
    assert checks(*run) == {"payload_missing"}


def test_bad_signature_detected(run: tuple[Path, Path], tmp_path: Path) -> None:
    conn = raw(run[0])
    d = get_json(conn, 2)
    d["signature"] = Signer(tmp_path / "other_keys").sign(d["record_hash"])
    put_json(conn, 2, d)
    assert checks(*run) == {"signature"}


def test_wrong_public_key_detected(run: tuple[Path, Path], tmp_path: Path) -> None:
    other = Signer(tmp_path / "other_keys").public_key
    assert {p.check for p in verify_run(run[0], public_key=other)} == {"signature"}


def test_truncation_detected_via_summary(run: tuple[Path, Path]) -> None:
    with EventStore.for_run(run[0]) as s:
        last = s.last()
        assert last is not None
        s.set_summary({"event_count": s.count(), "head_hash": last.record_hash})
    assert verify_run(run[0], keys_dir=run[1]) == []
    conn = raw(run[0])
    conn.execute("DELETE FROM events WHERE seq=(SELECT MAX(seq) FROM events)")
    conn.commit()
    assert {"truncated", "head_hash"} <= checks(*run)


def test_missing_log(tmp_path: Path) -> None:
    assert {p.check for p in verify_run(tmp_path, keys_dir=tmp_path)} == {"missing_log"}


def test_cli_verify_log(tmp_data_dir: Path) -> None:
    run_dir = tmp_data_dir / "runs" / "run1"
    build_run(run_dir, tmp_data_dir / "keys")
    runner = CliRunner()
    ok = runner.invoke(app, ["verify-log", "--run", "run1"])
    assert ok.exit_code == 0, ok.output
    assert "OK" in ok.output
    conn = raw(run_dir)
    conn.execute("DELETE FROM events WHERE seq=3")
    conn.commit()
    bad = runner.invoke(app, ["verify-log", "--run", "run1"])
    assert bad.exit_code == 1
    assert "seq_gap" in bad.output
