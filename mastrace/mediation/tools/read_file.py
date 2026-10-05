"""`read_file(path)`: read a file under the run's `env/files/` (internal)."""

from __future__ import annotations

from typing import Any

from mastrace.core.schemas import EventKind, ToolResult
from mastrace.mediation.tools.base import Tool, ToolContext


def _run(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    rel = str(args["path"]).strip().lstrip("/")
    rel = rel.removeprefix("files/")
    root = (ctx.env_dir / "files").resolve()
    target = (root / rel).resolve()
    if not target.is_relative_to(root):
        return ToolResult(
            output=f"Access denied: {args['path']} is outside files/", status="denied"
        )
    if not target.is_file():
        return ToolResult(output=f"File not found: {args['path']}", status="error")
    return ToolResult(output=target.read_text(encoding="utf-8"))


READ_FILE = Tool(
    name="read_file",
    source="internal",
    event_kind=EventKind.TOOL_CALL,
    args=("path",),
    run=_run,
    description="Read a text file. Paths are relative to files/.",
    cacheable=True,
)
