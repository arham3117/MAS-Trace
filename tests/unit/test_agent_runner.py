"""P3.3: ContextBuilder and AgentRunner."""

from __future__ import annotations

from pathlib import Path

import pytest

from mastrace.core.protocol import render_task
from mastrace.core.schemas import EventKind, GraphConfig, ModelRequest, ModelResponse
from mastrace.environment.materializer import materialize
from mastrace.environment.tasks import load_task
from mastrace.mediation.budget import TokenBudget
from mastrace.mediation.cache import ResponseCache
from mastrace.mediation.model_gateway import ModelGateway
from mastrace.mediation.providers.base import ModelProvider
from mastrace.mediation.providers.scripted import ScriptedProvider
from mastrace.mediation.router import InboxItem
from mastrace.mediation.tool_gateway import ToolGateway
from mastrace.runtime.agent_runner import AgentRunner
from mastrace.runtime.context_builder import ContextBuilder
from mastrace.runtime.graph_config import load_graph
from mastrace.runtime.prompts import render_system_prompt

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "env"


def runner(
    tmp_path: Path, provider: ModelProvider, cfg: GraphConfig | None = None, budget: int = 60000
) -> AgentRunner:
    cfg = cfg or load_graph("s1_chain")
    env = tmp_path / "env"
    snap = materialize(FIXTURES / "t_test", env, seed=1)
    cache = ResponseCache(tmp_path / "cache.sqlite")
    mgw = ModelGateway(provider, cache, TokenBudget(budget))
    tgw = ToolGateway(env, snap, {a.id: a.tools for a in cfg.agents}, cache=cache)
    prompts = {a.id: render_system_prompt(cfg, a.id, ["team@acme.example"]) for a in cfg.agents}
    return AgentRunner(cfg, mgw, tgw, prompts)


def task_item() -> InboxItem:
    t = load_task("t_test", FIXTURES)
    return InboxItem("r:000002", "user", render_task(t.instruction, t.sources), kind="task")


def test_researcher_turn_events(tmp_path: Path) -> None:
    r = runner(tmp_path, ScriptedProvider("gullible"))
    res = r.run_turn("A", [task_item()], superstep=1)
    assert res.turn_id == "A#1"
    kinds = [d.kind for d in res.buffer.drafts]
    assert kinds == [
        EventKind.MODEL_CALL,
        EventKind.EXTERNAL_READ,
        EventKind.MODEL_CALL,
        EventKind.EXTERNAL_READ,
        EventKind.MODEL_CALL,
    ]
    assert [d.call_index for d in res.buffer.drafts] == [0, 0, 1, 1, 2]
    assert [(m.to, m.order) for m in res.outgoing] == [("B", 0)]
    assert "FACT: A costs 10 dollars per seat per month." in res.outgoing[0].content
    assert res.outgoing[0].built_from == "local:A#1:4"
    assert res.final_output is None


def test_built_from_complete(tmp_path: Path) -> None:
    r = runner(tmp_path, ScriptedProvider("gullible"))
    res = r.run_turn("A", [task_item()], superstep=1)
    m0, t0, m1, t1, m2 = res.buffer.drafts
    assert m0.built_from == ["r:000002"]
    assert t0.built_from == ["local:A#1:0"]
    assert m1.built_from == ["r:000002", "local:A#1:0", "local:A#1:1"]
    assert m2.built_from == ["r:000002", "local:A#1:0", "local:A#1:1", "local:A#1:2", "local:A#1:3"]
    assert t1.built_from == ["local:A#1:2"]


def test_history_carries_across_turns(tmp_path: Path) -> None:
    r = runner(tmp_path, ScriptedProvider("gullible"), cfg=load_graph("s2_two_way_chain"))
    r.run_turn("B", [InboxItem("r:000010", "A", "FACT: x")], superstep=2)
    res = r.run_turn("B", [InboxItem("r:000020", "A", "FEEDBACK: received (1)")], superstep=4)
    assert res.turn_id == "B#2"
    assert res.buffer.drafts[0].built_from == ["r:000010", "local:B#1:0", "r:000020"]
    assert res.outgoing == []


def test_sink_final_output_event(tmp_path: Path) -> None:
    r = runner(tmp_path, ScriptedProvider("gullible"))
    res = r.run_turn("E", [InboxItem("r:000030", "D", "# Report\n\nFACT: x")], superstep=4)
    kinds = [d.kind for d in res.buffer.drafts]
    assert kinds == [
        EventKind.MODEL_CALL,
        EventKind.TOOL_CALL,
        EventKind.MODEL_CALL,
        EventKind.FINAL_OUTPUT,
    ]
    assert res.final_output == "# Report\n\nFACT: x"
    assert res.buffer.drafts[-1].built_from == ["local:E#1:2"]
    assert (tmp_path / "env" / "outbox.jsonl").exists()


class ScriptedTexts:
    name = "texts"

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self.identity = "texts/" + "|".join(texts)
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(text=self.texts.pop(0), prompt_tokens=1, completion_tokens=1)


def test_parse_failure_retry_then_success(tmp_path: Path) -> None:
    prov = ScriptedTexts(
        "not json", '{"action": "respond", "messages": [{"to": "C", "content": "ok"}]}'
    )
    res = runner(tmp_path, prov).run_turn("B", [InboxItem("r:000010", "A", "FACT: x")], 2)
    assert len(res.buffer.drafts) == 2
    assert "not a valid action" in prov.requests[1].messages[-1].content
    assert [(m.to, m.content) for m in res.outgoing] == [("C", "ok")]
    assert not res.parse_fallback


def test_parse_failure_twice_falls_back(tmp_path: Path) -> None:
    prov = ScriptedTexts("garbage one", "garbage two")
    res = runner(tmp_path, prov).run_turn("B", [InboxItem("r:000010", "A", "FACT: x")], 2)
    assert res.parse_fallback
    assert res.buffer.drafts[-1].meta["parse_fallback"] is True
    assert "parse_fallback" not in res.buffer.drafts[0].meta
    assert [(m.to, m.content) for m in res.outgoing] == [("C", "garbage two")]


def test_tool_cap_forces_respond(tmp_path: Path) -> None:
    tool = '{"action": "tool", "tool": "read_file", "args": {"path": "internal/policy.md"}}'
    prov = ScriptedTexts(*([tool] * 5))
    res = runner(tmp_path, prov).run_turn("D", [InboxItem("r:000010", "C", "x")], 3)
    kinds = [d.kind for d in res.buffer.drafts]
    assert kinds.count(EventKind.MODEL_CALL) == 5 and kinds.count(EventKind.TOOL_CALL) == 4
    assert "You must respond now." in prov.requests[-1].messages[-1].content
    assert res.outgoing == []


def test_invalid_target_passed_to_router(tmp_path: Path) -> None:
    prov = ScriptedTexts('{"action": "respond", "messages": [{"to": "E", "content": "skip"}]}')
    res = runner(tmp_path, prov).run_turn("B", [InboxItem("r:000010", "A", "x")], 2)
    assert [m.to for m in res.outgoing] == ["E"]


def test_non_sink_final_output_ignored(tmp_path: Path) -> None:
    prov = ScriptedTexts('{"action": "respond", "messages": [], "final_output": "done"}')
    res = runner(tmp_path, prov).run_turn("B", [InboxItem("r:000010", "A", "x")], 2)
    assert res.final_output is None
    assert all(d.kind != EventKind.FINAL_OUTPUT for d in res.buffer.drafts)


def test_budget_exceeded_ends_turn(tmp_path: Path) -> None:
    res = runner(tmp_path, ScriptedProvider("gullible"), budget=10).run_turn("A", [task_item()], 1)
    assert res.budget_exceeded and res.outgoing == []
    assert len(res.buffer.drafts) == 1


def test_context_builder_render() -> None:
    cb = ContextBuilder("sys")
    cb.add_inbox(InboxItem("e1", "A", "hello"))
    cb.add_model_output("{}", "local:B#1:0")
    cb.add_note("note")
    cb.add_tool_result("web_fetch", "page", "local:B#1:1")
    msgs, bf = cb.render()
    assert [m.role for m in msgs] == ["system", "user", "assistant", "user", "user"]
    assert msgs[1].content == "[MESSAGE from A]\nhello"
    assert msgs[4].content == "[TOOL RESULT web_fetch]\npage"
    assert bf == ["e1", "local:B#1:0", "local:B#1:1"]


@pytest.mark.parametrize("agent", ["A", "B", "C", "D", "E"])
def test_system_prompt_has_profile(agent: str) -> None:
    from mastrace.core.protocol import parse_profile

    cfg = load_graph("s1_chain")
    p = parse_profile(render_system_prompt(cfg, agent, ["team@acme.example"]))
    assert p.agent_id == agent and p.out_neighbours == cfg.out_neighbours(agent)
