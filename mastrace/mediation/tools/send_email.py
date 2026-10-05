"""`send_email(to, subject, body)`: append to the run's `env/outbox.jsonl` (action).

Never sends anything real.
"""

from __future__ import annotations

from typing import Any

from mastrace.core.canonical import canonical_json
from mastrace.core.schemas import EventKind, ToolResult
from mastrace.mediation.tools.base import Tool, ToolContext

OUTBOX = "outbox.jsonl"


def _run(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    record = {
        "from": ctx.agent_id,
        "to": str(args["to"]),
        "subject": str(args["subject"]),
        "body": str(args["body"]),
    }
    with (ctx.env_dir / OUTBOX).open("a", encoding="utf-8") as f:
        f.write(canonical_json(record) + "\n")
    return ToolResult(output=f"Email sent to {record['to']}")


SEND_EMAIL = Tool(
    name="send_email",
    source="action",
    event_kind=EventKind.TOOL_CALL,
    args=("to", "subject", "body"),
    run=_run,
    description="Send an email (to, subject, body).",
)
