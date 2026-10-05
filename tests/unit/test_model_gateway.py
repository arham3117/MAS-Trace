"""P2.2: model gateway modes, overrides, budget and events."""

from __future__ import annotations

from pathlib import Path

import pytest

from mastrace.core.errors import BudgetExceeded, CacheMiss
from mastrace.core.schemas import (
    ChatMessage,
    EventKind,
    ModelOutputOverride,
    ModelRequest,
    ModelResponse,
)
from mastrace.mediation.budget import TokenBudget
from mastrace.mediation.cache import ResponseCache
from mastrace.mediation.model_gateway import Mode, ModelGateway
from mastrace.provenance.recorder import EventBuffer


class SpyProvider:
    name = "spy"
    identity = "spy-model"

    def __init__(self, tokens: int = 10) -> None:
        self.calls: list[ModelRequest] = []
        self.tokens = tokens

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        return ModelResponse(
            text=f"answer {len(self.calls)}", prompt_tokens=self.tokens, completion_tokens=1
        )


MSGS = [ChatMessage(role="system", content="sys"), ChatMessage(role="user", content="hi")]


def gw(
    tmp_path: Path,
    provider: SpyProvider,
    mode: Mode = "record",
    limit: int = 10_000,
    overrides: list[ModelOutputOverride] | None = None,
) -> ModelGateway:
    return ModelGateway(
        provider,
        ResponseCache(tmp_path / "cache.sqlite"),
        TokenBudget(limit),
        mode=mode,
        overrides=overrides or [],
        seed=1,
    )


def buf() -> EventBuffer:
    return EventBuffer(agent_id="A", turn_id="A#1", superstep=1)


def test_record_then_replay_hits_cache(tmp_path: Path) -> None:
    spy = SpyProvider()
    b = buf()
    first = gw(tmp_path, spy).call("A", "A#1", 0, MSGS, ["r:000001"], b)
    assert len(spy.calls) == 1
    replay_spy = SpyProvider()
    b2 = buf()
    g2 = gw(tmp_path, replay_spy, mode="replay")
    second = g2.call("A", "A#1", 0, MSGS, ["r:000001"], b2)
    assert replay_spy.calls == []
    assert second.response == first.response
    assert b2.drafts[0].meta["cache_hit"] is True
    assert b.drafts[0].request_hash == b2.drafts[0].request_hash
    assert g2.stats() == {"calls": 1, "live_calls": 0}


def test_replay_miss_calls_live_and_flags(tmp_path: Path) -> None:
    spy = SpyProvider()
    b = buf()
    gw(tmp_path, spy, mode="replay").call("A", "A#1", 0, MSGS, [], b)
    assert len(spy.calls) == 1
    assert b.drafts[0].meta["cache_miss"] is True


def test_strict_replay_miss_raises(tmp_path: Path) -> None:
    b = buf()
    with pytest.raises(CacheMiss):
        gw(tmp_path, SpyProvider(), mode="strict_replay").call("A", "A#1", 0, MSGS, [], b)
    assert b.drafts == []


def test_model_output_override(tmp_path: Path) -> None:
    spy = SpyProvider()
    o = ModelOutputOverride(agent="A", turn=1, call_index=1, replacement='{"action":"respond"}')
    g = gw(tmp_path, spy, mode="replay", overrides=[o])
    b = buf()
    r0 = g.call("A", "A#1", 0, MSGS, [], b)
    r1 = g.call("A", "A#1", 1, [*MSGS, ChatMessage(role="user", content="x")], [], b)
    assert r0.text == "answer 1"
    assert r1.text == '{"action":"respond"}'
    assert len(spy.calls) == 1
    assert b.drafts[1].meta["override"] is True


def test_override_matches_logical_position_only(tmp_path: Path) -> None:
    o = ModelOutputOverride(agent="B", turn=1, call_index=0, replacement="X")
    r = gw(tmp_path, SpyProvider(), overrides=[o]).call("A", "A#1", 0, MSGS, [], buf())
    assert r.text != "X"


def test_budget_exceeded_after_recording(tmp_path: Path) -> None:
    g = gw(tmp_path, SpyProvider(tokens=40), limit=50)
    b = buf()
    g.call("A", "A#1", 0, MSGS, [], b)
    with pytest.raises(BudgetExceeded):
        g.call("A", "A#1", 1, MSGS + MSGS, [], b)
    assert len(b.drafts) == 2  # the call that broke the budget is still logged
    assert g.stats()["calls"] == 2


def test_event_contents(tmp_path: Path) -> None:
    b = buf()
    r = gw(tmp_path, SpyProvider()).call("A", "A#1", 0, MSGS, ["r:000001", "r:000002"], b)
    d = b.drafts[0]
    assert r.event_ref == "local:A#1:0"
    assert d.kind == EventKind.MODEL_CALL and d.call_index == 0 and d.turn_id == "A#1"
    assert d.built_from == ["r:000001", "r:000002"]
    assert d.output_text == "answer 1"
    assert d.input_text is not None and '"content":"hi"' in d.input_text
    assert d.meta["model"] == "spy-model"
    assert d.meta["params"] == {"temperature": 0.0, "max_tokens": 1024, "seed": 1}
    assert d.meta["tokens"] == {"prompt": 10, "completion": 1}


def test_cache_key_depends_on_provider_identity(tmp_path: Path) -> None:
    from mastrace.mediation.providers.scripted import ScriptedProvider

    a = ScriptedProvider("gullible")
    b = ScriptedProvider("gullible", policy_overrides={"C": "resistant"})
    assert a.identity != b.identity


def test_replay_salt_isolates_replays(tmp_path: Path) -> None:
    """Pre-override calls hit the recorded entry; post-override calls are per-replay."""
    cache = ResponseCache(tmp_path / "cache.sqlite")
    spy = SpyProvider()

    def gw_(mode: Mode, salt: str | None) -> ModelGateway:
        return ModelGateway(spy, cache, TokenBudget(10_000), mode=mode, seed=1, replay_salt=salt)

    recorded = gw_("record", None).call("A", "A#1", 0, MSGS, [], buf()).text
    assert recorded == "answer 1"
    new_msgs = [*MSGS, ChatMessage(role="user", content="diverged")]
    r1 = gw_("replay", "r1")
    r2 = gw_("replay", "r2")
    assert r1.call("A", "A#1", 0, MSGS, [], buf()).text == recorded  # recorded entry
    assert r2.call("A", "A#1", 0, MSGS, [], buf()).text == recorded
    a = r1.call("A", "A#1", 1, new_msgs, [], buf()).text
    b = r2.call("A", "A#1", 1, new_msgs, [], buf()).text
    assert (a, b) == ("answer 2", "answer 3")  # live each time, not shared
    assert gw_("replay", "r1").call("A", "A#1", 1, new_msgs, [], buf()).text == a  # stable
    assert len(spy.calls) == 3
