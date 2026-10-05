"""P2.1: LiteLLMProvider (unit tests with a fake `completion`, plus one `model` test)."""

from __future__ import annotations

import socket
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import pytest
from litellm import exceptions as llm_exc

from mastrace.core.errors import ConfigError
from mastrace.core.schemas import ChatMessage, ModelRequest
from mastrace.mediation.providers import ScriptedProvider, make_provider
from mastrace.mediation.providers.litellm_provider import LiteLLMProvider
from mastrace.settings import load_model

REQ = ModelRequest(
    model="dev_open", messages=[ChatMessage(role="user", content="hi")], max_tokens=5, seed=3
)


def fake_response(text: str) -> Any:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=7, completion_tokens=2),
    )


def test_passes_params_and_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://model-host.test:11434")
    seen: dict[str, Any] = {}

    def completion(**kw: Any) -> Any:
        seen.update(kw)
        return fake_response("ok")

    resp = LiteLLMProvider(load_model("dev_open"), completion=completion).complete(REQ)
    assert resp.text == "ok" and resp.total_tokens == 9
    assert seen["temperature"] == 0 and seen["seed"] == 3 and seen["max_tokens"] == 5
    assert seen["api_base"] == "http://model-host.test:11434"
    assert seen["messages"] == [{"role": "user", "content": "hi"}]


def test_retries_transient_errors(caplog: pytest.LogCaptureFixture) -> None:
    calls = {"n": 0}
    sleeps: list[float] = []

    def completion(**kw: Any) -> Any:
        calls["n"] += 1
        if calls["n"] < 3:
            raise llm_exc.APIConnectionError(message="down", llm_provider="ollama", model="m")
        return fake_response("ok")

    p = LiteLLMProvider(load_model("dev_open"), completion=completion, sleep=sleeps.append)
    with caplog.at_level("WARNING", logger="mastrace"):
        assert p.complete(REQ).text == "ok"
    assert calls["n"] == 3 and sleeps == [1.0, 2.0]
    assert sum("retry" in r.message for r in caplog.records) == 2


def test_gives_up_after_three_retries() -> None:
    calls = {"n": 0}

    def completion(**kw: Any) -> Any:
        calls["n"] += 1
        raise llm_exc.Timeout(message="slow", model="m", llm_provider="ollama")

    p = LiteLLMProvider(load_model("dev_open"), completion=completion, sleep=lambda s: None)
    with pytest.raises(llm_exc.Timeout):
        p.complete(REQ)
    assert calls["n"] == 4


def test_non_transient_error_not_retried() -> None:
    calls = {"n": 0}

    def completion(**kw: Any) -> Any:
        calls["n"] += 1
        raise ValueError("bad request")

    with pytest.raises(ValueError):
        LiteLLMProvider(load_model("dev_open"), completion=completion).complete(REQ)
    assert calls["n"] == 1


def test_factory() -> None:
    assert isinstance(make_provider(load_model("scripted_gullible")), ScriptedProvider)
    assert isinstance(make_provider(load_model("dev_open")), LiteLLMProvider)
    with pytest.raises(ConfigError):
        make_provider(load_model("commercial"))


def _dev_model_reachable() -> bool:
    base = load_model("dev_open").api_base()
    if not base:
        return False
    u = urlparse(base)
    try:
        with socket.create_connection((u.hostname or "", u.port or 80), timeout=1):
            return True
    except OSError:
        return False


@pytest.mark.model
def test_dev_model_live() -> None:
    if not _dev_model_reachable():
        pytest.skip("dev_open model server not reachable")
    resp = make_provider(load_model("dev_open")).complete(
        ModelRequest(
            model="dev_open",
            messages=[ChatMessage(role="user", content="Reply with the single word: pong")],
            max_tokens=10,
            seed=1,
        )
    )
    assert resp.text.strip()
