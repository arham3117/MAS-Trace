"""Per-run append-only SQLite event store (plan.md §7.5, P1.5).

The `events` table has no update or delete path in this module, and SQLite triggers abort
any UPDATE or DELETE on it. `alerts`, `verdicts` and `run_summary` hold derived data.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path
from types import TracebackType
from typing import Any

from mastrace.core.canonical import canonical_json
from mastrace.core.errors import EventNotFound, OutOfOrderAppend
from mastrace.core.schemas import Alert, EventKind, EventRecord, Verdict

DB_FILE = "events.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq         INTEGER PRIMARY KEY,
    event_id    TEXT NOT NULL UNIQUE,
    kind        TEXT NOT NULL,
    actor       TEXT NOT NULL,
    turn_id     TEXT,
    record_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor);
CREATE INDEX IF NOT EXISTS idx_events_turn ON events(turn_id);
CREATE INDEX IF NOT EXISTS idx_events_seq ON events(seq);
CREATE TRIGGER IF NOT EXISTS events_append_only_u BEFORE UPDATE ON events
    BEGIN SELECT RAISE(ABORT, 'events table is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_append_only_d BEFORE DELETE ON events
    BEGIN SELECT RAISE(ABORT, 'events table is append-only'); END;

CREATE TABLE IF NOT EXISTS alerts (
    alert_seq    INTEGER PRIMARY KEY AUTOINCREMENT,
    detector     TEXT NOT NULL,
    severity     TEXT NOT NULL,
    event_id     TEXT NOT NULL,
    details_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verdicts (
    verdict_id   TEXT PRIMARY KEY,
    method       TEXT NOT NULL,
    status       TEXT NOT NULL,
    verdict_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_summary (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    summary_json TEXT NOT NULL
);
"""


class EventStore:
    """Append-only event log for one run, plus alerts, verdicts and a run summary."""

    def __init__(self, path: Path, readonly: bool = False) -> None:
        self.path = path
        self.readonly = readonly
        if readonly:
            self._conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    @classmethod
    def for_run(cls, run_dir: Path, readonly: bool = False) -> EventStore:
        """Open `<run_dir>/events.sqlite`."""
        return cls(run_dir / DB_FILE, readonly=readonly)

    # -- lifecycle -------------------------------------------------------------

    def close(self) -> None:
        """Close the connection."""
        self._conn.close()

    def __enter__(self) -> EventStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- events ------------------------------------------------------------------

    def _next_seq(self) -> int:
        row = self._conn.execute("SELECT MAX(seq) FROM events").fetchone()
        return int(row[0] or 0) + 1

    def append(self, record: EventRecord) -> None:
        """Append one event. Its `seq` must be exactly the next one."""
        self.append_many([record])

    def append_many(self, records: Iterable[EventRecord]) -> None:
        """Append several events in one transaction, each with the next `seq`."""
        with self._conn:
            expected = self._next_seq()
            for r in records:
                if r.seq != expected:
                    raise OutOfOrderAppend(f"expected seq {expected}, got {r.seq} ({r.event_id})")
                self._conn.execute(
                    "INSERT INTO events (seq, event_id, kind, actor, turn_id, record_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        r.seq,
                        r.event_id,
                        r.kind.value,
                        r.actor,
                        r.turn_id,
                        canonical_json(r.model_dump(mode="json")),
                    ),
                )
                expected += 1

    def get(self, event_id: str) -> EventRecord:
        """Return one event by ID, raising `EventNotFound` if absent."""
        row = self._conn.execute(
            "SELECT record_json FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            raise EventNotFound(event_id)
        return EventRecord.model_validate_json(row[0])

    def iter(self, kind: EventKind | None = None) -> Iterator[EventRecord]:
        """Iterate events in `seq` order, optionally of one kind."""
        if kind is None:
            cur = self._conn.execute("SELECT record_json FROM events ORDER BY seq")
        else:
            cur = self._conn.execute(
                "SELECT record_json FROM events WHERE kind = ? ORDER BY seq", (kind.value,)
            )
        for (raw,) in cur.fetchall():
            yield EventRecord.model_validate_json(raw)

    def count(self) -> int:
        """Number of events."""
        return int(self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def last(self) -> EventRecord | None:
        """The event with the highest `seq`, or None if the log is empty."""
        row = self._conn.execute(
            "SELECT record_json FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return None if row is None else EventRecord.model_validate_json(row[0])

    # -- derived data --------------------------------------------------------------

    def add_alert(self, alert: Alert) -> None:
        """Record a detector alert."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO alerts (detector, severity, event_id, details_json) "
                "VALUES (?, ?, ?, ?)",
                (alert.detector, alert.severity, alert.event_id, canonical_json(alert.details)),
            )

    def alerts(self) -> list[Alert]:
        """All alerts in insertion order."""
        rows = self._conn.execute(
            "SELECT detector, severity, event_id, details_json FROM alerts ORDER BY alert_seq"
        ).fetchall()
        return [
            Alert(detector=d, severity=s, event_id=e, details=json.loads(j)) for d, s, e, j in rows
        ]

    def add_verdict(self, verdict: Verdict) -> None:
        """Record a verdict. Verdict IDs are unique."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO verdicts (verdict_id, method, status, verdict_json) "
                "VALUES (?, ?, ?, ?)",
                (verdict.verdict_id, verdict.method, verdict.status, verdict.model_dump_json()),
            )

    def verdicts(self) -> list[Verdict]:
        """All verdicts in insertion order."""
        rows = self._conn.execute("SELECT verdict_json FROM verdicts ORDER BY rowid").fetchall()
        return [Verdict.model_validate_json(r[0]) for r in rows]

    def set_summary(self, summary: dict[str, Any]) -> None:
        """Store (or replace) the run summary."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO run_summary (id, summary_json) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET summary_json = excluded.summary_json",
                (canonical_json(summary),),
            )

    def summary(self) -> dict[str, Any] | None:
        """The run summary, if set."""
        row = self._conn.execute("SELECT summary_json FROM run_summary WHERE id = 1").fetchone()
        return None if row is None else dict(json.loads(row[0]))
