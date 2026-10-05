"""Request-hash cache shared by all runs: `data/cache/model_cache.sqlite` (plan.md §7.7)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from mastrace.core.schemas import ModelResponse, ToolResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_cache (
    request_hash  TEXT PRIMARY KEY,
    model         TEXT NOT NULL,
    request_json  TEXT NOT NULL,
    response_json TEXT NOT NULL,
    origin        TEXT NOT NULL DEFAULT 'record'
);
CREATE TABLE IF NOT EXISTS tool_cache (
    request_hash  TEXT PRIMARY KEY,
    tool          TEXT NOT NULL,
    result_json   TEXT NOT NULL
);
"""


class ResponseCache:
    """Maps request hashes to model responses and tool results. First write wins."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._conn = sqlite3.connect(path, timeout=30)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(model_cache)")}
        if "origin" not in cols:  # caches created before ISSUE-008
            self._conn.execute(
                "ALTER TABLE model_cache ADD COLUMN origin TEXT NOT NULL DEFAULT 'record'"
            )
        self._conn.commit()

    def close(self) -> None:
        """Close the connection."""
        self._conn.close()

    def get_model(self, request_hash: str, origin: str | None = None) -> ModelResponse | None:
        """Cached model response, if any (only entries written with `origin`, if given)."""
        row = self._conn.execute(
            "SELECT response_json, origin FROM model_cache WHERE request_hash = ?",
            (request_hash,),
        ).fetchone()
        if row is None or (origin is not None and row[1] != origin):
            return None
        return ModelResponse.model_validate_json(row[0])

    def put_model(
        self,
        request_hash: str,
        model: str,
        request_json: str,
        response: ModelResponse,
        origin: str = "record",
    ) -> None:
        """Store a model response (ignored if the hash is already cached)."""
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO model_cache "
                "(request_hash, model, request_json, response_json, origin) VALUES (?, ?, ?, ?, ?)",
                (request_hash, model, request_json, response.model_dump_json(), origin),
            )

    def get_tool(self, request_hash: str) -> ToolResult | None:
        """Cached tool result, if any."""
        row = self._conn.execute(
            "SELECT result_json FROM tool_cache WHERE request_hash = ?", (request_hash,)
        ).fetchone()
        return None if row is None else ToolResult.model_validate_json(row[0])

    def put_tool(self, request_hash: str, tool: str, result: ToolResult) -> None:
        """Store a tool result (ignored if the hash is already cached)."""
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO tool_cache VALUES (?, ?, ?)",
                (request_hash, tool, result.model_dump_json()),
            )
