"""Integrity verification of a run's event log (plan.md §7.6, P1.7).

Reads the raw `events` rows (not through `EventStore`) so that malformed or reordered rows
are reported as problems instead of raising.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from mastrace.core.errors import InvalidPayloadRef
from mastrace.core.schemas import EventRecord
from mastrace.provenance.event_store import DB_FILE, EventStore
from mastrace.provenance.payload_store import PayloadStore
from mastrace.provenance.recorder import GENESIS, compute_record_hash
from mastrace.provenance.signer import load_public_key, verify


class Problem(BaseModel):
    """One integrity violation."""

    check: str
    seq: int | None = None
    event_id: str | None = None
    detail: str = ""


def verify_run(
    run_dir: Path, public_key: str | None = None, keys_dir: Path | None = None
) -> list[Problem]:
    """Check seq contiguity, the hash chain, record hashes, signatures and payloads.

    The public key is `public_key` if given, else read from `keys_dir` (default: settings).
    """
    problems: list[Problem] = []
    db = run_dir / DB_FILE
    if not db.is_file():
        return [Problem(check="missing_log", detail=str(db))]
    if public_key is None:
        if keys_dir is None:
            from mastrace.settings import get_settings

            keys_dir = get_settings().keys_dir
        assert keys_dir is not None
        try:
            public_key = load_public_key(keys_dir)
        except FileNotFoundError:
            problems.append(Problem(check="no_public_key", detail=str(keys_dir)))

    payloads = PayloadStore(run_dir / "payloads")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows: list[tuple[int, str, str]] = conn.execute(
            "SELECT seq, event_id, record_json FROM events ORDER BY seq"
        ).fetchall()
    finally:
        conn.close()

    expected_seq = 1
    prev_hash = GENESIS
    for row_seq, row_id, raw in rows:
        try:
            rec = EventRecord.model_validate_json(raw)
        except ValidationError as e:
            problems.append(Problem(check="malformed", seq=row_seq, detail=str(e)[:200]))
            expected_seq = row_seq + 1
            prev_hash = ""
            continue
        p = _Checker(problems, rec)
        if row_seq != expected_seq:
            p.add("seq_gap", f"expected seq {expected_seq}, found {row_seq}")
        if rec.seq != row_seq or rec.event_id != row_id:
            p.add(
                "row_mismatch", f"row seq/id {row_seq}/{row_id} vs record {rec.seq}/{rec.event_id}"
            )
        if rec.event_id != f"{rec.run_id}:{rec.seq:06d}":
            p.add("bad_event_id", rec.event_id)
        if rec.prev_hash != prev_hash:
            p.add("prev_hash", f"prev_hash {rec.prev_hash[:12]} != {prev_hash[:12]}")
        actual = compute_record_hash(rec.hashable_dict())
        if actual != rec.record_hash:
            p.add("record_hash", f"stored {rec.record_hash[:12]}, computed {actual[:12]}")
        if public_key is not None and not verify(rec.record_hash, rec.signature, public_key):
            p.add("signature", "signature does not verify")
        for name in ("input_ref", "output_ref"):
            ref = getattr(rec, name)
            if ref is None:
                continue
            try:
                if not payloads.exists(ref):
                    p.add("payload_missing", f"{name} {ref}")
                elif not payloads.verify(ref):
                    p.add("payload_corrupt", f"{name} {ref}")
            except InvalidPayloadRef:
                p.add("payload_ref_invalid", f"{name} {ref}")
        expected_seq = row_seq + 1
        prev_hash = rec.record_hash

    problems.extend(_check_summary(run_dir, len(rows), prev_hash))
    return problems


class _Checker:
    def __init__(self, problems: list[Problem], rec: EventRecord) -> None:
        self.problems = problems
        self.rec = rec

    def add(self, check: str, detail: str) -> None:
        self.problems.append(
            Problem(check=check, seq=self.rec.seq, event_id=self.rec.event_id, detail=detail)
        )


def _check_summary(run_dir: Path, count: int, head: str) -> list[Problem]:
    """If the run summary records the final event count / head hash, check them (truncation)."""
    with EventStore.for_run(run_dir, readonly=True) as store:
        summary: dict[str, Any] | None = store.summary()
    if not summary:
        return []
    out = []
    if "event_count" in summary and summary["event_count"] != count:
        out.append(
            Problem(
                check="truncated", detail=f"summary says {summary['event_count']}, log has {count}"
            )
        )
    if "head_hash" in summary and summary["head_hash"] != head:
        out.append(Problem(check="head_hash", detail="last record hash differs from summary"))
    return out
