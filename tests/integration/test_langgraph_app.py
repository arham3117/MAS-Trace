"""P3.4: the LangGraph run loop with the scripted provider."""

from __future__ import annotations

from pathlib import Path

from mastrace.core.protocol import (
    OutMessage,
    RespondAction,
    dump_action,
    parse_profile,
    render_task,
)
from mastrace.core.schemas import EventKind, GraphConfig, ModelRequest, ModelResponse
from mastrace.environment.materializer import materialize
from mastrace.environment.tasks import load_task
from mastrace.mediation.budget import TokenBudget
from mastrace.mediation.cache import ResponseCache
from mastrace.mediation.model_gateway import ModelGateway
from mastrace.mediation.providers.base import ModelProvider
from mastrace.mediation.providers.scripted import ScriptedProvider
from mastrace.mediation.router import Router
from mastrace.mediation.tool_gateway import ToolGateway
from mastrace.provenance.event_store import EventStore
from mastrace.provenance.payload_store import PayloadStore
from mastrace.provenance.recorder import EventDraft, Recorder
from mastrace.provenance.signer import Signer
from mastrace.runtime.agent_runner import AgentRunner
from mastrace.runtime.graph_config import load_graph
from mastrace.runtime.langgraph_app import RunContext, RunState, run_graph
from mastrace.runtime.prompts import render_system_prompt

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "env"


def run(tmp_path: Path, cfg: GraphConfig, provider: ModelProvider) -> tuple[RunState, Recorder]:
    task = load_task("t_test", FIXTURES)
    env = tmp_path / "env"
    snap = materialize(FIXTURES / "t_test", env, seed=1)
    rec = Recorder(
        "r",
        cfg.stage,
        EventStore.for_run(tmp_path),
        PayloadStore(tmp_path / "p"),
        Signer(tmp_path / "keys"),
        "x",
    )
    budget = TokenBudget(cfg.limits.max_tokens_run)
    cache = ResponseCache(tmp_path / "cache.sqlite")
    router = Router(cfg, rec, budget)
    runner = AgentRunner(
        cfg,
        ModelGateway(provider, cache, budget),
        ToolGateway(env, snap, {a.id: a.tools for a in cfg.agents}, cache=cache),
        {a.id: render_system_prompt(cfg, a.id, task.allowed_recipients) for a in cfg.agents},
    )
    for agent in cfg.entry_agents:
        body = render_task(task.instruction, task.sources)
        ev = rec.record_now(
            EventDraft(
                kind=EventKind.TASK_INPUT,
                actor="user",
                superstep=0,
                receivers=[agent],
                output_text=body,
            )
        )
        router.put_task(agent, ev.event_id, body)
    state = run_graph(RunContext(cfg, router, runner, rec, budget), thread_id="r")
    return state, rec


def test_s1_chain_completes(tmp_path: Path) -> None:
    state, rec = run(tmp_path, load_graph("s1_chain"), ScriptedProvider("gullible"))
    assert state["status"] == "completed"
    assert state["final_output"] is not None
    assert state["final_output"].startswith("# Report")
    assert state["superstep"] == 5
    turns = [e.turn_id for e in rec.store.iter(EventKind.MODEL_CALL)]
    assert list(dict.fromkeys(turns)) == ["A#1", "B#1", "C#1", "D#1", "E#1"]
    assert len(list(rec.store.iter(EventKind.FINAL_OUTPUT))) == 1


class PingPong:
    """Always messages every out-neighbour: never ends on its own."""

    name = "pingpong"
    identity = "pingpong"

    def complete(self, request: ModelRequest) -> ModelResponse:
        p = parse_profile(request.messages[0].content)
        action = RespondAction(
            action="respond", messages=[OutMessage(to=n, content="ping") for n in p.out_neighbours]
        )
        return ModelResponse(text=dump_action(action), prompt_tokens=1, completion_tokens=1)


def test_looping_config_stops_at_superstep_limit(tmp_path: Path) -> None:
    cfg = load_graph("s2_two_way_chain").model_copy(deep=True)
    cfg.limits.max_supersteps = 6
    cfg.limits.max_messages_per_direction = 100
    state, _ = run(tmp_path, cfg, PingPong())
    assert state["status"] == "stopped_superstep_limit"
    assert state["superstep"] == 6


def test_budget_stops_run(tmp_path: Path) -> None:
    cfg = load_graph("s1_chain").model_copy(deep=True)
    cfg.limits.max_tokens_run = 2000
    state, _ = run(tmp_path, cfg, ScriptedProvider("gullible"))
    assert state["status"] == "stopped_budget"


def test_idle_when_sink_never_reached(tmp_path: Path) -> None:
    state, _ = run(
        tmp_path, load_graph("s1_chain"), ScriptedProvider("gullible", policy_overrides={})
    )
    assert state["status"] == "completed"
    cfg = load_graph("s1_chain")

    class Silent:
        name = identity = "silent"

        def complete(self, request: ModelRequest) -> ModelResponse:
            return ModelResponse(text='{"action": "respond", "messages": []}')

    state, _ = run(tmp_path / "silent", cfg, Silent())
    assert state["status"] == "stopped_idle"
