"""P4.2: rendered system prompts (snapshot tests).

Regenerate snapshots after an intended prompt change with:
    UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/test_prompts.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from mastrace.core.protocol import parse_profile
from mastrace.runtime.graph_config import load_graph
from mastrace.runtime.prompts import TWO_WAY_LINE, render_system_prompt

SNAP_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "snapshots" / "prompts"
TEAM = ["team@acme.example"]
CASES = [("s1_chain", a) for a in "ABCDE"] + [("s1_fanin", "B")]


@pytest.mark.parametrize(("config", "agent"), CASES)
def test_prompt_snapshot(config: str, agent: str) -> None:
    text = render_system_prompt(load_graph(config), agent, TEAM)
    snap = SNAP_DIR / f"{config}_{agent}.txt"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1" or not snap.exists():
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(text, encoding="utf-8")
    assert text == snap.read_text(encoding="utf-8")


@pytest.mark.parametrize("agent", list("ABCDE"))
def test_no_unfilled_placeholders(agent: str) -> None:
    for config in ["s1_chain", "s2_two_way_chain", "s3_mixed_two_paths"]:
        text = render_system_prompt(load_graph(config), agent, TEAM)
        for key in [
            "neighbours",
            "tools",
            "allowed_recipients",
            "is_sink",
            "agent_id",
            "two_way_line",
            "max_tool_calls",
        ]:
            assert "{" + key + "}" not in text


def test_prompt_states_required_items() -> None:
    cfg = load_graph("s1_chain")
    text = render_system_prompt(cfg, "E", TEAM)
    assert "operator" in text and "team@acme.example" in text
    assert "send_email" in text and '"action": "respond"' in text
    assert "you are the final agent" in text.lower()
    assert parse_profile(text).is_sink


def test_two_way_line_only_with_two_way_links() -> None:
    assert TWO_WAY_LINE not in render_system_prompt(load_graph("s1_chain"), "B", TEAM)
    assert TWO_WAY_LINE in render_system_prompt(load_graph("s2_two_way_chain"), "B", TEAM)
    mixed = load_graph("s3_mixed_two_paths")
    assert TWO_WAY_LINE not in render_system_prompt(mixed, "C", TEAM)
    assert TWO_WAY_LINE in render_system_prompt(mixed, "D", TEAM)
