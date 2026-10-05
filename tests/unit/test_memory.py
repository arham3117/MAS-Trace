"""P2.4: memory service."""

from __future__ import annotations

import json
from pathlib import Path

from mastrace.core.schemas import EventKind
from mastrace.mediation.memory import MemoryService
from mastrace.mediation.tool_gateway import ToolGateway
from mastrace.provenance.recorder import EventBuffer


def test_missing_key_is_none_version_0() -> None:
    assert MemoryService().read("A", "k") == (None, 0)


def test_version_increments() -> None:
    m = MemoryService()
    assert m.write("A", "k", "v1") == 1
    assert m.write("A", "k", "v2") == 2
    assert m.read("A", "k") == ("v2", 2)


def test_private_and_shared_namespaces() -> None:
    m = MemoryService()
    m.write("A", "k", "a")
    assert m.read("B", "k") == (None, 0)
    m.write("A", "shared/k", "s")
    assert m.read("B", "shared/k") == ("s", 1)
    assert m.write("B", "shared/k", "t") == 2


def test_reads_and_writes_are_events(tmp_path: Path) -> None:
    g = ToolGateway(tmp_path, "h", {"A": ["memory_read", "memory_write"]})
    b = EventBuffer(agent_id="A", turn_id="A#1", superstep=1)
    g.call("A", "A#1", 0, "memory_write", {"key": "k", "value": "v"}, [], b)
    r = g.call("A", "A#1", 1, "memory_read", {"key": "k"}, [], b)
    miss = g.call("A", "A#1", 2, "memory_read", {"key": "other"}, [], b)
    assert [d.kind for d in b.drafts] == [
        EventKind.MEMORY_WRITE,
        EventKind.MEMORY_READ,
        EventKind.MEMORY_READ,
    ]
    assert json.loads(r.result.output) == {"key": "k", "value": "v", "version": 1}
    assert json.loads(miss.result.output) == {"key": "other", "value": None, "version": 0}
