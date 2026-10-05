"""Ground-truth store: `data/ground_truth.sqlite` (plan.md §7.9, I8).

Only `mastrace.control` (the injector) and `mastrace.evaluation` may import this package.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from mastrace.core.schemas import GroundTruth

_SCHEMA = "CREATE TABLE IF NOT EXISTS ground_truth (run_id TEXT PRIMARY KEY, gt_json TEXT NOT NULL)"


class GroundTruthStore:
    """One row per run: what the injector did."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, timeout=30)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def put(self, gt: GroundTruth) -> None:
        """Store the ground truth of a run (a re-run with the same ID replaces it)."""
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO ground_truth VALUES (?, ?)",
                (gt.run_id, gt.model_dump_json()),
            )

    def get(self, run_id: str) -> GroundTruth | None:
        """Ground truth of a run, or None for runs without an injection."""
        row = self._conn.execute(
            "SELECT gt_json FROM ground_truth WHERE run_id = ?", (run_id,)
        ).fetchone()
        return None if row is None else GroundTruth.model_validate_json(row[0])

    def close(self) -> None:
        """Close the connection."""
        self._conn.close()

    def __enter__(self) -> GroundTruthStore:
        return self

    def __exit__(
        self, t: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()
