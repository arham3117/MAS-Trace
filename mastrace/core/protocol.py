"""The text contract between the runtime and the models (plan.md §7.3, §7.13).

Three things are defined here so that the `ContextBuilder` (which writes prompts) and the
`ScriptedProvider` (which reads them) agree exactly:

1. The **agent profile** block at the end of every system prompt (`## Agent profile`).
2. The **item headers** that mark each prompt item: `[TASK from user]`, `[MESSAGE from B]`,
   `[TOOL RESULT web_fetch]`, `[NOTE]`.
3. The **JSON action protocol** an agent must answer with (`tool` or `respond`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

PROFILE_HEADING = "## Agent profile"
SOURCE_PREFIX = "SOURCE:"
FACT_PREFIX = "FACT:"
FEEDBACK_PREFIX = "FEEDBACK:"
MUST_RESPOND_NOTE = "You must respond now."

# --------------------------------------------------------------------------- agent profile


@dataclass(frozen=True)
class AgentProfile:
    """Machine-readable facts about one agent, rendered into its system prompt."""

    agent_id: str
    role: str
    out_neighbours: list[str]
    tools: list[str]
    is_sink: bool
    allowed_recipients: list[str]
    two_way_with: list[str] = field(default_factory=list)


def render_profile(p: AgentProfile) -> str:
    """Render the profile block (appended to the role prompt)."""

    def join(xs: list[str]) -> str:
        return ", ".join(xs) if xs else "(none)"

    return "\n".join(
        [
            PROFILE_HEADING,
            f"agent_id: {p.agent_id}",
            f"role: {p.role}",
            f"out_neighbours: {join(p.out_neighbours)}",
            f"two_way_with: {join(p.two_way_with)}",
            f"tools: {join(p.tools)}",
            f"is_sink: {'yes' if p.is_sink else 'no'}",
            f"allowed_recipients: {join(p.allowed_recipients)}",
        ]
    )


def parse_profile(system_text: str) -> AgentProfile:
    """Parse the profile block out of a system prompt."""
    if PROFILE_HEADING not in system_text:
        raise ValueError("system prompt has no agent profile block")
    block = system_text.split(PROFILE_HEADING, 1)[1]
    kv: dict[str, str] = {}
    for line in block.strip().splitlines():
        k, sep, v = line.partition(":")
        if not sep:
            break
        kv[k.strip()] = v.strip()

    def split(key: str) -> list[str]:
        v = kv.get(key, "(none)")
        return [] if v == "(none)" else [x.strip() for x in v.split(",") if x.strip()]

    return AgentProfile(
        agent_id=kv["agent_id"],
        role=kv["role"],
        out_neighbours=split("out_neighbours"),
        two_way_with=split("two_way_with"),
        tools=split("tools"),
        is_sink=kv.get("is_sink") == "yes",
        allowed_recipients=split("allowed_recipients"),
    )


# --------------------------------------------------------------------------- prompt items

ItemKind = Literal["task", "message", "tool_result", "note"]
_HEADER = re.compile(
    r"\A\[(?:(TASK) from (\S+)|(MESSAGE) from (\S+)|(TOOL RESULT) (\S+)|(NOTE))\]\n?"
)


@dataclass(frozen=True)
class PromptItem:
    """A parsed user-side prompt item."""

    kind: ItemKind
    source: str  # sender agent ID, "user", or tool name ("" for notes)
    content: str


def render_item(kind: ItemKind, source: str, content: str) -> str:
    """Render one user-side prompt item with its header line."""
    header = {
        "task": f"[TASK from {source}]",
        "message": f"[MESSAGE from {source}]",
        "tool_result": f"[TOOL RESULT {source}]",
        "note": "[NOTE]",
    }[kind]
    return f"{header}\n{content}"


def parse_item(text: str) -> PromptItem | None:
    """Parse a rendered item; None if the text has no recognised header."""
    m = _HEADER.match(text)
    if m is None:
        return None
    content = text[m.end() :]
    if m.group(1):
        return PromptItem("task", m.group(2), content)
    if m.group(3):
        return PromptItem("message", m.group(4), content)
    if m.group(5):
        return PromptItem("tool_result", m.group(6), content)
    return PromptItem("note", "", content)


def render_task(instruction: str, sources: list[str]) -> str:
    """Body of a `task_input` item: the instruction, then one `SOURCE:` line per URL."""
    lines = [instruction.strip()]
    if sources:
        lines.append("")
        lines.extend(f"{SOURCE_PREFIX} {u}" for u in sources)
    return "\n".join(lines)


def task_sources(task_text: str) -> list[str]:
    """URLs listed on `SOURCE:` lines of a task body, in order."""
    return [
        line[len(SOURCE_PREFIX) :].strip()
        for line in task_text.splitlines()
        if line.startswith(SOURCE_PREFIX)
    ]


# --------------------------------------------------------------------------- actions


class OutMessage(BaseModel):
    """One outgoing message in a `respond` action."""

    model_config = ConfigDict(extra="ignore")

    to: str
    content: str


class ToolAction(BaseModel):
    """`{"action": "tool", "tool": ..., "args": {...}}`."""

    model_config = ConfigDict(extra="ignore")

    action: Literal["tool"]
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class RespondAction(BaseModel):
    """`{"action": "respond", "messages": [...], "final_output": ...}`."""

    model_config = ConfigDict(extra="ignore")

    action: Literal["respond"]
    messages: list[OutMessage] = Field(default_factory=list)
    final_output: str | None = None


Action = Annotated[ToolAction | RespondAction, Field(discriminator="action")]
_ACTION: TypeAdapter[ToolAction | RespondAction] = TypeAdapter(Action)


class ProtocolError(ValueError):
    """A model response is not a valid action."""


_FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.S)


def parse_action(text: str) -> ToolAction | RespondAction:
    """Parse a model response into an action.

    Accepts bare JSON, JSON in a ```json fence, or the first `{...}` object in the text.
    """
    candidates = [text.strip()]
    m = _FENCE.search(text)
    if m:
        candidates.append(m.group(1))
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start : end + 1])
    last_err: Exception | None = None
    for c in candidates:
        try:
            return _ACTION.validate_python(json.loads(c))
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = e
    raise ProtocolError(f"not a valid action: {last_err}")


def dump_action(action: ToolAction | RespondAction) -> str:
    """Serialize an action as compact, key-sorted JSON (deterministic)."""
    return json.dumps(action.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
