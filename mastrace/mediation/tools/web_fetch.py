"""`web_fetch(url)`: serve pages from the run's `env/web/<host>/<path>.md` (external)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from mastrace.core.schemas import EventKind, ToolResult
from mastrace.mediation.tools.base import Tool, ToolContext

NOT_FOUND = "404 Not Found"


def _run(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    u = urlparse(str(args["url"]).strip())
    if u.scheme not in ("http", "https") or not u.hostname:
        return ToolResult(output=NOT_FOUND)
    path = u.path.strip("/") or "index"
    web_root = (ctx.env_dir / "web").resolve()
    page = (web_root / u.hostname / f"{path}.md").resolve()
    if not page.is_relative_to(web_root) or not page.is_file():
        return ToolResult(output=NOT_FOUND)
    return ToolResult(output=page.read_text(encoding="utf-8"))


WEB_FETCH = Tool(
    name="web_fetch",
    source="external",
    event_kind=EventKind.EXTERNAL_READ,
    args=("url",),
    run=_run,
    description="Fetch a web page by URL and return its text.",
    cacheable=True,
)
