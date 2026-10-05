"""Per-agent conversation history with source tags (plan.md §7.3-7.4, P3.3).

Every user-side item and every model output is tagged with the event it came from, so the
`built_from` of a model call is exactly the events whose content is in its prompt (I4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mastrace.core.protocol import render_item
from mastrace.core.schemas import ChatMessage
from mastrace.mediation.router import InboxItem


@dataclass(frozen=True)
class ContextItem:
    """One prompt item and the event it came from (None for notes)."""

    source: str | None
    role: Literal["user", "assistant"]
    text: str


class ContextBuilder:
    """The full history of one agent across turns."""

    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self.items: list[ContextItem] = []

    def add_inbox(self, item: InboxItem) -> None:
        """Append a delivered task or message, tagged with its event ID."""
        kind: Literal["task", "message"] = item.kind
        self.items.append(
            ContextItem(item.event_id, "user", render_item(kind, item.sender, item.content))
        )

    def add_model_output(self, text: str, event_ref: str) -> None:
        """Append the agent's own model output, tagged with its `model_call` event."""
        self.items.append(ContextItem(event_ref, "assistant", text))

    def add_tool_result(self, tool: str, output: str, event_ref: str) -> None:
        """Append a tool result, tagged with its tool event."""
        self.items.append(ContextItem(event_ref, "user", render_item("tool_result", tool, output)))

    def add_note(self, text: str) -> None:
        """Append a runtime note (no source event)."""
        self.items.append(ContextItem(None, "user", render_item("note", "", text)))

    def render(self) -> tuple[list[ChatMessage], list[str]]:
        """The message list for the model, and `built_from` (sources in order, no repeats)."""
        messages = [ChatMessage(role="system", content=self.system_prompt)]
        messages += [ChatMessage(role=i.role, content=i.text) for i in self.items]
        built_from = list(dict.fromkeys(i.source for i in self.items if i.source is not None))
        return messages, built_from
