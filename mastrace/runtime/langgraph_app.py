"""The run loop as a LangGraph graph: START → router ⇄ agents_step → END (plan.md §7.2, P3.4).

Runtime objects (router, runner, recorder) live in a `RunContext` captured by the nodes;
the LangGraph state holds a plain-data snapshot (superstep, inboxes, counters, tokens,
status, final output) for inspection and checkpointing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from mastrace.core.schemas import EventRecord, GraphConfig
from mastrace.mediation.budget import TokenBudget
from mastrace.mediation.router import Router
from mastrace.provenance.recorder import Recorder
from mastrace.runtime.agent_runner import AgentRunner, TurnResult

CommitHook = Callable[[list[EventRecord]], None]


class RunState(TypedDict):
    """Plain-data view of a run between nodes."""

    superstep: int
    status: str | None
    final_output: str | None
    tokens: int
    inboxes: dict[str, list[str]]
    counters: dict[str, int]


@dataclass
class RunContext:
    """Everything the nodes need. Only the router node commits and delivers."""

    cfg: GraphConfig
    router: Router
    runner: AgentRunner
    recorder: Recorder
    budget: TokenBudget
    on_commit: list[CommitHook] = field(default_factory=list)
    pending: list[TurnResult] = field(default_factory=list)
    final_output: str | None = None


def initial_state() -> RunState:
    """State at superstep 0 (task inputs are already in the inboxes)."""
    return RunState(superstep=0, status=None, final_output=None, tokens=0, inboxes={}, counters={})


def _snapshot(ctx: RunContext) -> dict[str, Any]:
    return {
        "inboxes": {a: [i.event_id for i in items] for a, items in ctx.router.inboxes.items()},
        "counters": {f"{s}->{r}": n for (s, r), n in sorted(ctx.router.accepted.items())},
        "tokens": ctx.budget.used,
        "final_output": ctx.final_output,
    }


def build_app(ctx: RunContext) -> Any:
    """Compile the graph for one run."""

    def router_node(state: RunState) -> dict[str, Any]:
        superstep = state["superstep"]
        results = sorted(ctx.pending, key=lambda r: r.buffer.sort_key())
        ctx.pending = []
        committed = ctx.recorder.commit([r.buffer for r in results]).records
        for r in results:
            if r.final_output is not None:
                ctx.final_output = r.final_output
        delivered = ctx.router.deliver([m for r in results for m in r.outgoing], superstep)
        for hook in ctx.on_commit:
            hook(committed + delivered)
        status = ctx.router.decide(superstep, ctx.final_output is not None)
        return {"status": status, **_snapshot(ctx)}

    def agents_step(state: RunState) -> dict[str, Any]:
        superstep = state["superstep"] + 1
        for agent_id in ctx.router.agents_with_mail():
            items = ctx.router.take_inbox(agent_id)
            ctx.pending.append(ctx.runner.run_turn(agent_id, items, superstep))
        return {"superstep": superstep, **_snapshot(ctx)}

    def route(state: RunState) -> str:
        return END if state["status"] is not None else "agents_step"

    graph = StateGraph(RunState)
    graph.add_node("router", router_node)
    graph.add_node("agents_step", agents_step)
    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", route, {"agents_step": "agents_step", END: END})
    graph.add_edge("agents_step", "router")
    return graph.compile(checkpointer=InMemorySaver())


def recursion_limit(cfg: GraphConfig) -> int:
    """`2 * max_supersteps + 5` (§7.2 rule 5)."""
    return 2 * cfg.limits.max_supersteps + 5


def run_graph(ctx: RunContext, thread_id: str) -> RunState:
    """Run the graph to completion and return the final state."""
    app = build_app(ctx)
    final: RunState = app.invoke(
        initial_state(),
        config={
            "recursion_limit": recursion_limit(ctx.cfg),
            "configurable": {"thread_id": thread_id},
        },
    )
    return final
