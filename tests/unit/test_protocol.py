"""core/protocol.py: text contract and lenient action parsing."""

from __future__ import annotations

import pytest

from mastrace.core.protocol import (
    AgentProfile,
    ProtocolError,
    RespondAction,
    ToolAction,
    dump_action,
    parse_action,
    parse_item,
    parse_profile,
    render_item,
    render_profile,
    render_task,
    task_sources,
)

TOOL = '{"action": "tool", "tool": "web_fetch", "args": {"url": "https://a.example/p"}}'


def test_bare_json() -> None:
    a = parse_action(TOOL)
    assert isinstance(a, ToolAction) and a.args["url"] == "https://a.example/p"


def test_fenced_json() -> None:
    assert isinstance(parse_action(f"Sure!\n```json\n{TOOL}\n```"), ToolAction)


def test_several_actions_takes_first() -> None:
    text = TOOL + "\n" + TOOL.replace("a.example", "b.example") + '\n{"action": "respond"}'
    a = parse_action(text)
    assert isinstance(a, ToolAction) and a.args["url"] == "https://a.example/p"


def test_prose_around_json() -> None:
    a = parse_action('I will now respond. {"action": "respond", "messages": []} Thanks.')
    assert isinstance(a, RespondAction) and a.messages == []


def test_skips_non_action_objects() -> None:
    a = parse_action('{"note": 1} then ' + TOOL)
    assert isinstance(a, ToolAction)


@pytest.mark.parametrize(
    "bad", ["", "no json here", '{"action": "dance"}', '{"action": "tool"}', "[1, 2]", "{broken"]
)
def test_invalid(bad: str) -> None:
    with pytest.raises(ProtocolError):
        parse_action(bad)


def test_dump_round_trip() -> None:
    a = parse_action(
        '{"action":"respond","messages":[{"to":"B","content":"x"}],"final_output":null}'
    )
    assert parse_action(dump_action(a)) == a


def test_profile_round_trip() -> None:
    p = AgentProfile("B", "analyst", ["A", "C"], [], False, ["team@acme.example"], ["A"])
    assert parse_profile("Role text.\n\n" + render_profile(p)) == p


def test_items_and_task() -> None:
    assert parse_item(render_item("message", "A", "hi\nthere")).content == "hi\nthere"  # type: ignore[union-attr]
    assert parse_item("no header") is None
    body = render_task("Do it.", ["https://a.example/x", "https://b.example/y"])
    assert task_sources(body) == ["https://a.example/x", "https://b.example/y"]


def test_tool_name_as_action_is_a_tool_call() -> None:
    a = parse_action('{"action": "send_email", "args": {"to": "t", "subject": "s", "body": "b"}}')
    assert isinstance(a, ToolAction) and a.tool == "send_email"
    b = parse_action('{"action": "send_email", "tool": "send_email", "args": {"to": "t"}}')
    assert isinstance(b, ToolAction) and b.tool == "send_email"
    with pytest.raises(ProtocolError):
        parse_action('{"action": "dance", "args": "nope"}')
