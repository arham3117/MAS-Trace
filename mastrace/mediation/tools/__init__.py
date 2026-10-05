"""Tool registry (plan.md §7.8)."""

from __future__ import annotations

from mastrace.mediation.tools.base import Tool, ToolContext, ToolSource
from mastrace.mediation.tools.memory_tools import MEMORY_READ, MEMORY_WRITE
from mastrace.mediation.tools.read_file import READ_FILE
from mastrace.mediation.tools.send_email import SEND_EMAIL
from mastrace.mediation.tools.web_fetch import WEB_FETCH

REGISTRY: dict[str, Tool] = {
    t.name: t for t in (WEB_FETCH, READ_FILE, SEND_EMAIL, MEMORY_READ, MEMORY_WRITE)
}


def tool_names() -> set[str]:
    """Names of every registered tool."""
    return set(REGISTRY)


__all__ = ["REGISTRY", "Tool", "ToolContext", "ToolSource", "tool_names"]
