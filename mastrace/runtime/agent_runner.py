"""One agent turn: prompt, model, tools, respond (plan.md §7.3, P3.3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from mastrace.core.errors import BudgetExceeded
from mastrace.core.ids import turn_id
from mastrace.core.logging import get_logger
from mastrace.core.protocol import MUST_RESPOND_NOTE, ProtocolError, ToolAction, parse_action
from mastrace.core.schemas import EventKind, GraphConfig
from mastrace.mediation.model_gateway import ModelGateway
from mastrace.mediation.router import InboxItem, OutgoingMessage
from mastrace.mediation.tool_gateway import ToolGateway
from mastrace.provenance.recorder import EventBuffer
from mastrace.runtime.context_builder import ContextBuilder

log = get_logger("agent_runner")

PARSE_RETRY_NOTE = (
    "Your last reply was not a valid action ({error}). "
    "Reply with exactly one JSON object as described in the protocol."
)


@dataclass
class TurnResult:
    """Everything a turn produced; the router commits `buffer` and delivers `outgoing`."""

    agent_id: str
    turn_id: str
    buffer: EventBuffer
    outgoing: list[OutgoingMessage] = field(default_factory=list)
    final_output: str | None = None
    budget_exceeded: bool = False
    parse_fallback: bool = False


class AgentRunner:
    """Runs agent turns. Agents reach models and tools only through the gateways (I1)."""

    def __init__(
        self,
        cfg: GraphConfig,
        model_gateway: ModelGateway,
        tool_gateway: ToolGateway,
        system_prompts: Mapping[str, str],
    ) -> None:
        self.cfg = cfg
        self.model_gateway = model_gateway
        self.tool_gateway = tool_gateway
        self.contexts = {a.id: ContextBuilder(system_prompts[a.id]) for a in cfg.agents}
        self.turns: dict[str, int] = {a.id: 0 for a in cfg.agents}

    def run_turn(self, agent_id: str, new_inbox: Sequence[InboxItem], superstep: int) -> TurnResult:
        """Run one turn of `agent_id` on its newly delivered items."""
        self.turns[agent_id] += 1
        tid = turn_id(agent_id, self.turns[agent_id])
        result = TurnResult(agent_id, tid, EventBuffer(agent_id, tid, superstep))
        ctx = self.contexts[agent_id]
        for item in new_inbox:
            ctx.add_inbox(item)
        try:
            self._loop(agent_id, tid, ctx, result)
        except BudgetExceeded:
            log.warning("%s: token budget exceeded; turn ends without messages", tid)
            result.budget_exceeded = True
            result.outgoing = []
        return result

    def _loop(self, agent_id: str, tid: str, ctx: ContextBuilder, result: TurnResult) -> None:
        cap = self.cfg.limits.max_tool_calls_per_turn
        buf = result.buffer
        tool_calls = model_calls = 0
        noted = retried = False
        while True:
            if tool_calls >= cap and not noted:
                ctx.add_note(MUST_RESPOND_NOTE)
                noted = True
            messages, built_from = ctx.render()
            res = self.model_gateway.call(agent_id, tid, model_calls, messages, built_from, buf)
            model_calls += 1
            ctx.add_model_output(res.text, res.event_ref)
            try:
                action = parse_action(res.text)
            except ProtocolError as e:
                if not retried:
                    retried = True
                    ctx.add_note(PARSE_RETRY_NOTE.format(error=str(e)[:200]))
                    continue
                buf.drafts[-1].meta["parse_fallback"] = True
                result.parse_fallback = True
                log.warning("%s: unparseable output twice; sending raw text", tid)
                result.outgoing = [
                    OutgoingMessage(agent_id, n, res.text, res.event_ref, i)
                    for i, n in enumerate(self.cfg.out_neighbours(agent_id))
                ]
                return
            retried = False
            if isinstance(action, ToolAction):
                if tool_calls >= cap:
                    log.warning("%s: tool call after the cap; ending turn", tid)
                    return
                tr = self.tool_gateway.call(
                    agent_id, tid, tool_calls, action.tool, action.args, [res.event_ref], buf
                )
                tool_calls += 1
                ctx.add_tool_result(action.tool, tr.result.output, tr.event_ref)
                continue
            result.outgoing = [
                OutgoingMessage(agent_id, m.to, m.content, res.event_ref, i)
                for i, m in enumerate(action.messages)
            ]
            if action.final_output is not None:
                if agent_id == self.cfg.sink_agent:
                    result.final_output = action.final_output
                    buf.add(
                        EventKind.FINAL_OUTPUT,
                        built_from=[res.event_ref],
                        output_text=action.final_output,
                    )
                else:
                    log.warning("%s: final_output from a non-sink agent ignored", tid)
            return
