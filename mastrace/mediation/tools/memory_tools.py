"""`memory_read(key)` / `memory_write(key, value)` through the `MemoryService` (internal)."""

from __future__ import annotations

from typing import Any

from mastrace.core.canonical import canonical_json
from mastrace.core.schemas import EventKind, ToolResult
from mastrace.mediation.tools.base import Tool, ToolContext


def _read(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    value, version = ctx.memory.read(ctx.agent_id, str(args["key"]))
    return ToolResult(
        output=canonical_json({"key": args["key"], "value": value, "version": version})
    )


def _write(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    version = ctx.memory.write(ctx.agent_id, str(args["key"]), str(args["value"]))
    return ToolResult(output=canonical_json({"key": args["key"], "version": version}))


MEMORY_READ = Tool(
    name="memory_read",
    source="internal",
    event_kind=EventKind.MEMORY_READ,
    args=("key",),
    run=_read,
    description="Read a value from memory (keys starting with shared/ are shared).",
)

MEMORY_WRITE = Tool(
    name="memory_write",
    source="internal",
    event_kind=EventKind.MEMORY_WRITE,
    args=("key", "value"),
    run=_write,
    description="Write a value to memory (keys starting with shared/ are shared).",
)
