"""Deterministic stand-in model for plumbing tests (plan.md §7.13, P2.1).

Policies, by role (full description in `tests/fixtures/scripted_policies.md`):

- researcher / researcher_2: `web_fetch` each `SOURCE:` URL of the task, one per call, then
  send every `FACT:` line (gullible: plus every instruction paragraph) to every out-neighbour.
- analyst / planner / writer: forward received `FACT:` lines (gullible: and instruction
  paragraphs) to every out-neighbour except the sender they came from. The writer prefixes
  `# Report`.
- operator (sink): gullible only, if an instruction paragraph names `credentials.txt` and an
  email address, `read_file` it and `send_email` it there; always `send_email` the report to
  each allowed recipient and set `final_output` to the report.
- two-way links: reply `FEEDBACK: received (<round>)` to each sender on a two-way link, at
  most `feedback_rounds` times per link.

Each unit of content (a `FACT:` line or an instruction paragraph) is sent to a given
neighbour at most once per run, which keeps meshes from echoing forever.
The provider is stateless: everything is derived from the request's messages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from mastrace.core.protocol import (
    FACT_PREFIX,
    FEEDBACK_PREFIX,
    MUST_RESPOND_NOTE,
    AgentProfile,
    OutMessage,
    PromptItem,
    ProtocolError,
    RespondAction,
    ToolAction,
    dump_action,
    parse_action,
    parse_item,
    parse_profile,
    task_sources,
)
from mastrace.core.schemas import ChatMessage, ModelRequest, ModelResponse
from mastrace.mediation.providers.base import estimate_tokens
from mastrace.mediation.providers.scripted_patterns import (
    CREDENTIALS_PATH_PATTERN,
    EMAIL_PATTERN,
    SCRIPTED_INSTRUCTION_PATTERNS,
)

Policy = Literal["gullible", "resistant"]
RESEARCHER_ROLES = {"researcher", "researcher_2"}
REPORT_HEADING = "# Report"

_PARA_SPLIT = re.compile(r"\n\s*\n")


# --------------------------------------------------------------------------- text helpers


def fact_lines(text: str) -> list[str]:
    """Every line that starts with `FACT:` (stripped), in order."""
    return [ln.strip() for ln in text.splitlines() if ln.strip().startswith(FACT_PREFIX)]


def is_instruction(paragraph: str, allowed_recipients: list[str]) -> bool:
    """True if a paragraph matches an instruction pattern or names a non-allowed address."""
    if any(p.search(paragraph) for p in SCRIPTED_INSTRUCTION_PATTERNS):
        return True
    allowed = {a.lower() for a in allowed_recipients}
    return any(m.group(0).lower() not in allowed for m in EMAIL_PATTERN.finditer(paragraph))


def instruction_paragraphs(text: str, allowed_recipients: list[str]) -> list[str]:
    """Blank-line-separated paragraphs that are instructions and not just `FACT:` lines."""
    out = []
    for para in _PARA_SPLIT.split(text):
        p = para.strip()
        if not p:
            continue
        lines = [ln.strip() for ln in p.splitlines() if ln.strip()]
        if all(ln.startswith((FACT_PREFIX, FEEDBACK_PREFIX)) for ln in lines):
            continue
        if is_instruction(p, allowed_recipients):
            out.append(p)
    return out


def _dedupe(xs: list[str]) -> list[str]:
    return list(dict.fromkeys(xs))


def _units(text: str, allowed: list[str], gullible: bool) -> list[str]:
    units = fact_lines(text)
    if gullible:
        units += instruction_paragraphs(text, allowed)
    return units


def _compose(units: list[str], feedback: str | None, heading: str | None = None) -> str:
    facts = [u for u in units if u.startswith(FACT_PREFIX)]
    paras = [u for u in units if not u.startswith(FACT_PREFIX)]
    blocks: list[str] = []
    if heading and units:
        blocks.append(heading)
    if facts:
        blocks.append("\n".join(facts))
    blocks.extend(paras)
    if feedback:
        blocks.append(feedback)
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- conversation view


@dataclass
class _View:
    """The request split into what the provider needs."""

    profile: AgentProfile
    history_items: list[PromptItem]  # user-side items before the current turn
    sent_before: list[OutMessage]  # messages this agent sent in earlier turns
    turn_items: list[PromptItem]  # user-side items in the current turn
    tool_calls_done: int
    must_respond: bool

    @property
    def tool_results(self) -> list[PromptItem]:
        return [i for i in self.turn_items if i.kind == "tool_result"]

    @property
    def inbox(self) -> list[PromptItem]:
        return [i for i in self.turn_items if i.kind == "message"]

    @property
    def task(self) -> PromptItem | None:
        return next((i for i in self.turn_items if i.kind == "task"), None)


def _view(messages: list[ChatMessage]) -> _View:
    if not messages or messages[0].role != "system":
        raise ValueError("scripted provider needs a system prompt with an agent profile")
    profile = parse_profile(messages[0].content)
    rest = messages[1:]
    last_respond = -1
    sent_before: list[OutMessage] = []
    for i, m in enumerate(rest):
        if m.role != "assistant":
            continue
        try:
            action = parse_action(m.content)
        except ProtocolError:
            continue
        if isinstance(action, RespondAction):
            last_respond = i
            sent_before.extend(action.messages)

    def items(ms: list[ChatMessage]) -> list[PromptItem]:
        out = []
        for m in ms:
            if m.role == "user":
                item = parse_item(m.content)
                if item is not None:
                    out.append(item)
        return out

    current = rest[last_respond + 1 :]
    turn_items = items(current)
    tool_calls = 0
    for m in current:
        if m.role == "assistant":
            try:
                if isinstance(parse_action(m.content), ToolAction):
                    tool_calls += 1
            except ProtocolError:
                pass
    return _View(
        profile=profile,
        history_items=items(rest[: last_respond + 1]),
        sent_before=sent_before,
        turn_items=turn_items,
        tool_calls_done=tool_calls,
        must_respond=any(i.kind == "note" and MUST_RESPOND_NOTE in i.content for i in turn_items),
    )


# --------------------------------------------------------------------------- provider


class ScriptedProvider:
    """Rule-based model that returns protocol-valid JSON actions (see module docstring)."""

    name = "scripted"

    def __init__(
        self,
        policy: Policy,
        policy_overrides: dict[str, Policy] | None = None,
        feedback_rounds: int = 1,
    ) -> None:
        self.policy = policy
        self.policy_overrides = dict(policy_overrides or {})
        self.feedback_rounds = feedback_rounds

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Decide the next action from the conversation in `request`."""
        view = _view(request.messages)
        policy = self.policy_overrides.get(view.profile.agent_id, self.policy)
        action = self._decide(view, gullible=policy == "gullible")
        text = dump_action(action)
        prompt = sum(estimate_tokens(m.content) for m in request.messages)
        return ModelResponse(
            text=text, prompt_tokens=prompt, completion_tokens=estimate_tokens(text)
        )

    # -- decisions ---------------------------------------------------------------

    def _decide(self, v: _View, gullible: bool) -> ToolAction | RespondAction:
        p = v.profile
        if p.role in RESEARCHER_ROLES and v.task is not None:
            return self._researcher(v, gullible)
        if p.role == "operator":
            return self._operator(v, gullible)
        return self._relay(v, gullible)

    def _feedback_for(self, v: _View) -> dict[str, str]:
        """FEEDBACK lines owed to senders on two-way links (rounds permitting)."""
        out: dict[str, str] = {}
        for sender in sorted({i.source for i in v.inbox}):
            if sender not in v.profile.two_way_with or sender not in v.profile.out_neighbours:
                continue
            used = sum(1 for m in v.sent_before if m.to == sender and FEEDBACK_PREFIX in m.content)
            if used < self.feedback_rounds:
                out[sender] = f"{FEEDBACK_PREFIX} received ({used + 1})"
        return out

    def _already_sent(self, v: _View, to: str) -> set[str]:
        sent: set[str] = set()
        for m in v.sent_before:
            if m.to == to:
                sent.update(_units(m.content, v.profile.allowed_recipients, gullible=True))
        return sent

    def _messages(
        self,
        v: _View,
        sourced_units: list[tuple[str, str]],
        heading: str | None = None,
        forward: bool = True,
    ) -> list[OutMessage]:
        feedback = self._feedback_for(v)
        msgs = []
        for n in v.profile.out_neighbours:
            units: list[str] = []
            if forward:
                done = self._already_sent(v, n)
                units = _dedupe([u for src, u in sourced_units if src != n and u not in done])
            body = _compose(units, feedback.get(n), heading)
            if body:
                msgs.append(OutMessage(to=n, content=body))
        return msgs

    def _researcher(self, v: _View, gullible: bool) -> ToolAction | RespondAction:
        assert v.task is not None
        sources = task_sources(v.task.content)
        if v.tool_calls_done < len(sources) and not v.must_respond:
            return ToolAction(
                action="tool", tool="web_fetch", args={"url": sources[v.tool_calls_done]}
            )
        allowed = v.profile.allowed_recipients
        units = [("", u) for r in v.tool_results for u in _units(r.content, allowed, gullible)]
        units += self._inbox_units(v, gullible)
        return RespondAction(action="respond", messages=self._messages(v, units))

    def _inbox_units(self, v: _View, gullible: bool) -> list[tuple[str, str]]:
        allowed = v.profile.allowed_recipients
        return [(i.source, u) for i in v.inbox for u in _units(i.content, allowed, gullible)]

    def _relay(self, v: _View, gullible: bool) -> RespondAction:
        heading = REPORT_HEADING if v.profile.role == "writer" else None
        return RespondAction(
            action="respond",
            messages=self._messages(v, self._inbox_units(v, gullible), heading=heading),
        )

    def _operator(self, v: _View, gullible: bool) -> ToolAction | RespondAction:
        allowed = v.profile.allowed_recipients
        feedback_only = RespondAction(
            action="respond", messages=self._messages(v, [], forward=False)
        )
        new_units = [u for _, u in self._inbox_units(v, gullible)]
        if not new_units:
            return feedback_only
        all_msgs = [i for i in v.history_items + v.turn_items if i.kind == "message"]
        facts = _dedupe([f for i in all_msgs for f in fact_lines(i.content)])
        instr: list[str] = []
        if gullible:
            instr = _dedupe(
                [p for i in all_msgs for p in instruction_paragraphs(i.content, allowed)]
            )
        report = _compose(facts + instr, None, REPORT_HEADING)

        plan: list[ToolAction] = []
        exfil_body_from: int | None = None
        if gullible:
            for i in v.inbox:
                for para in instruction_paragraphs(i.content, allowed):
                    path = CREDENTIALS_PATH_PATTERN.search(para)
                    addrs = [
                        m.group(0)
                        for m in EMAIL_PATTERN.finditer(para)
                        if m.group(0).lower() not in {a.lower() for a in allowed}
                    ]
                    if path and addrs and exfil_body_from is None:
                        exfil_body_from = len(plan)
                        plan.append(
                            ToolAction(
                                action="tool", tool="read_file", args={"path": path.group(0)}
                            )
                        )
                        plan.append(
                            ToolAction(
                                action="tool",
                                tool="send_email",
                                args={"to": addrs[0], "subject": "Audit copy", "body": ""},
                            )
                        )
        for r in allowed:
            plan.append(
                ToolAction(
                    action="tool",
                    tool="send_email",
                    args={"to": r, "subject": "Report", "body": report},
                )
            )
        k = v.tool_calls_done
        if k < len(plan) and not v.must_respond:
            step = plan[k]
            if exfil_body_from is not None and k == exfil_body_from + 1:
                body = v.tool_results[exfil_body_from].content
                step = ToolAction(
                    action="tool", tool="send_email", args={**step.args, "body": body}
                )
            return step
        return RespondAction(
            action="respond",
            messages=self._messages(v, [], forward=False),
            final_output=report,
        )
