"""Versioned key-value memory per agent, plus a `shared` namespace (plan.md P2.4).

Keys that start with `shared/` live in the shared namespace; all others are private to the
agent. Every access goes through the tool gateway (`memory_read` / `memory_write`), which
records it as an event. State lives for one run, so replays start from the same empty state.
"""

from __future__ import annotations

SHARED_PREFIX = "shared/"
SHARED_NAMESPACE = "shared"


class MemoryService:
    """In-run versioned key-value store."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], tuple[str, int]] = {}

    @staticmethod
    def namespace(agent_id: str, key: str) -> str:
        """`shared` for `shared/...` keys, else the agent's own namespace."""
        return SHARED_NAMESPACE if key.startswith(SHARED_PREFIX) else f"agent:{agent_id}"

    def read(self, agent_id: str, key: str) -> tuple[str | None, int]:
        """Return `(value, version)`; a missing key is `(None, 0)`."""
        return self._data.get((self.namespace(agent_id, key), key), (None, 0))

    def write(self, agent_id: str, key: str, value: str) -> int:
        """Store `value` and return the new version (1 for the first write)."""
        ns = self.namespace(agent_id, key)
        _, version = self._data.get((ns, key), (None, 0))
        self._data[(ns, key)] = (value, version + 1)
        return version + 1
