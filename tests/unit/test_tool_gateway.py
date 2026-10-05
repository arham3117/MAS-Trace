"""P2.3: tools and the tool gateway."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastrace.core.schemas import EventKind, ToolOutputOverride
from mastrace.mediation.cache import ResponseCache
from mastrace.mediation.tool_gateway import ToolGateway
from mastrace.provenance.recorder import EventBuffer

PAGE = "# Pricing\n\nFACT: A costs 10."


@pytest.fixture
def env(tmp_path: Path) -> Path:
    e = tmp_path / "env"
    (e / "web" / "vendor-a.example").mkdir(parents=True)
    (e / "web" / "vendor-a.example" / "pricing.md").write_text(PAGE)
    (e / "web" / "vendor-a.example" / "index.md").write_text("home")
    (e / "files" / "internal").mkdir(parents=True)
    (e / "files" / "internal" / "policy.md").write_text("policy text")
    (tmp_path / "secret.txt").write_text("outside")
    return e


GRANTS = {
    "A": ["web_fetch"],
    "E": ["read_file", "send_email"],
    "M": ["memory_read", "memory_write"],
}


def gw(env: Path, **kw: object) -> ToolGateway:
    return ToolGateway(env, "envhash", GRANTS, **kw)  # type: ignore[arg-type]


def buf(agent: str = "A") -> EventBuffer:
    return EventBuffer(agent_id=agent, turn_id=f"{agent}#1", superstep=1)


def test_web_fetch_known_url(env: Path) -> None:
    b = buf()
    r = gw(env).call(
        "A", "A#1", 0, "web_fetch", {"url": "https://vendor-a.example/pricing"}, ["local:A#1:0"], b
    )
    assert r.result.output == PAGE and r.result.status == "ok"
    d = b.drafts[0]
    assert d.kind == EventKind.EXTERNAL_READ
    assert d.built_from == ["local:A#1:0"]
    assert d.output_text == PAGE
    assert d.meta["source"] == "external" and d.meta["status"] == "ok"


def test_web_fetch_root_is_index(env: Path) -> None:
    r = gw(env).call("A", "A#1", 0, "web_fetch", {"url": "https://vendor-a.example/"}, [], buf())
    assert r.result.output == "home"


@pytest.mark.parametrize(
    "url",
    [
        "https://vendor-a.example/missing",
        "https://other.example/x",
        "file:///etc/passwd",
        "https://vendor-a.example/../../secret",
    ],
)
def test_web_fetch_unknown_url_404(env: Path, url: str) -> None:
    r = gw(env).call("A", "A#1", 0, "web_fetch", {"url": url}, [], buf())
    assert r.result.output == "404 Not Found"


def test_read_file(env: Path) -> None:
    g = gw(env)
    for path in ["internal/policy.md", "files/internal/policy.md"]:
        b = buf("E")
        r = g.call("E", "E#1", 0, "read_file", {"path": path}, [], b)
        assert r.result.output == "policy text"
        assert b.drafts[0].kind == EventKind.TOOL_CALL and b.drafts[0].meta["source"] == "internal"


@pytest.mark.parametrize("path", ["../../secret.txt", "files/../../secret.txt", "/../secret.txt"])
def test_read_file_traversal_denied(env: Path, path: str) -> None:
    b = buf("E")
    r = gw(env).call("E", "E#1", 0, "read_file", {"path": path}, [], b)
    assert r.result.status == "denied"
    assert b.drafts[0].meta["status"] == "denied"
    assert "outside" not in r.result.output.replace("is outside files/", "")


def test_read_file_missing(env: Path) -> None:
    r = gw(env).call("E", "E#1", 0, "read_file", {"path": "nope.md"}, [], buf("E"))
    assert r.result.status == "error"


def test_send_email_writes_outbox(env: Path) -> None:
    b = buf("E")
    args = {"to": "team@acme.example", "subject": "Report", "body": "hello"}
    r = gw(env).call("E", "E#1", 0, "send_email", args, [], b)
    assert r.result.output == "Email sent to team@acme.example"
    lines = (env / "outbox.jsonl").read_text().splitlines()
    assert [json.loads(x) for x in lines] == [{"from": "E", **args}]
    assert b.drafts[0].meta["source"] == "action"


def test_denied_tool_recorded(env: Path) -> None:
    b = buf()
    args = {"to": "x@evil.example", "subject": "s", "body": "b"}
    r = gw(env).call("A", "A#1", 0, "send_email", args, [], b)
    assert r.result.status == "denied"
    assert "not available" in r.result.output
    assert b.drafts[0].meta["status"] == "denied"
    assert not (env / "outbox.jsonl").exists()


def test_unknown_tool_recorded(env: Path) -> None:
    b = buf()
    r = gw(env).call("A", "A#1", 0, "shell", {"cmd": "ls"}, [], b)
    assert r.result.status == "denied"
    assert b.drafts[0].kind == EventKind.TOOL_CALL


def test_invalid_args(env: Path) -> None:
    g = gw(env)
    assert g.call("A", "A#1", 0, "web_fetch", {}, [], buf()).result.status == "error"
    assert g.call("A", "A#1", 0, "web_fetch", {"url": 3}, [], buf()).result.status == "error"
    assert (
        g.call("A", "A#1", 0, "web_fetch", {"url": "u", "x": "y"}, [], buf()).result.status
        == "error"
    )


def test_override_applied(env: Path) -> None:
    o = ToolOutputOverride(agent="A", turn=1, call_index=1, replacement="[content unavailable]")
    g = gw(env, overrides=[o])
    b = buf()
    url = {"url": "https://vendor-a.example/pricing"}
    assert g.call("A", "A#1", 0, "web_fetch", url, [], b).result.output == PAGE
    r = g.call("A", "A#1", 1, "web_fetch", url, [], b)
    assert r.result.output == "[content unavailable]"
    assert b.drafts[1].meta["override"] is True
    assert b.drafts[1].output_text == "[content unavailable]"


def test_cache_hit_for_read_tools(env: Path, tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "c.sqlite")
    url = {"url": "https://vendor-a.example/pricing"}
    gw(env, cache=cache).call("A", "A#1", 0, "web_fetch", url, [], buf())
    (env / "web" / "vendor-a.example" / "pricing.md").write_text("changed")
    b = buf()
    r = gw(env, cache=cache).call("A", "A#1", 0, "web_fetch", url, [], b)
    assert r.result.output == PAGE and b.drafts[0].meta["cache_hit"] is True


def test_actions_never_cached(env: Path, tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "c.sqlite")
    args = {"to": "team@acme.example", "subject": "s", "body": "b"}
    for _ in range(2):
        gw(env, cache=cache).call("E", "E#1", 0, "send_email", args, [], buf("E"))
    assert len((env / "outbox.jsonl").read_text().splitlines()) == 2


def test_stats_count_every_call(env: Path) -> None:
    g = gw(env)
    g.call("A", "A#1", 0, "web_fetch", {"url": "https://vendor-a.example/pricing"}, [], buf())
    g.call("A", "A#1", 1, "send_email", {"to": "a", "subject": "b", "body": "c"}, [], buf())
    assert g.stats() == {"calls": 2}


def test_revoke(env: Path) -> None:
    g = gw(env)
    g.revoke("A")
    url = {"url": "https://vendor-a.example/pricing"}
    assert g.call("A", "A#1", 0, "web_fetch", url, [], buf()).result.status == "denied"
