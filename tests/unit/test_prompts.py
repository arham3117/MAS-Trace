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
CASES = (
    [("s1_chain", a, "summary") for a in "ABCDE"]
    + [("s1_chain", a, "fact_only") for a in "ABCDE"]
    + [("s1_chain", a, "full_context") for a in "ABCDE"]
    + [("s1_fanin", "B", "summary")]
)


@pytest.mark.parametrize(("config", "agent", "style"), CASES)
def test_prompt_snapshot(config: str, agent: str, style: str) -> None:
    text = render_system_prompt(load_graph(config), agent, TEAM, handoff_style=style)
    suffix = "" if style == "summary" else f"{style}_"
    snap = SNAP_DIR / f"{config}_{suffix}{agent}.txt"
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
    assert "- send_email(to, subject, body):" in text


def test_two_way_line_only_with_two_way_links() -> None:
    assert TWO_WAY_LINE not in render_system_prompt(load_graph("s1_chain"), "B", TEAM)
    assert TWO_WAY_LINE in render_system_prompt(load_graph("s2_two_way_chain"), "B", TEAM)
    mixed = load_graph("s3_mixed_two_paths")
    assert TWO_WAY_LINE not in render_system_prompt(mixed, "C", TEAM)
    assert TWO_WAY_LINE in render_system_prompt(mixed, "D", TEAM)


# -- answers.md D1c: handoff styles --------------------------------------------------------

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
FORBIDDEN = ["instruction", "notes addressed", "follow any", "comply", "obey", "prioriti"]


def test_no_prompt_tells_agents_to_relay_or_obey_instructions() -> None:
    """Hard rule: whether attacker text is relayed must be the model's own behaviour."""
    files = sorted(PROMPTS.rglob("*.md"))
    assert len(files) >= 1 + 6 + 3 * 6
    for f in files:
        text = f.read_text().lower()
        for phrase in FORBIDDEN:
            assert phrase not in text, (f.name, phrase)


@pytest.mark.parametrize("style", ["summary", "fact_only", "full_context"])
def test_every_role_has_every_style(style: str) -> None:
    for role in ["researcher", "researcher_2", "analyst", "planner", "writer", "operator"]:
        assert (PROMPTS / "handoff" / style / f"{role}.md").is_file()


def test_styles_differ_and_unknown_rejected() -> None:
    cfg = load_graph("s1_chain")
    texts = {
        s: render_system_prompt(cfg, "B", TEAM, handoff_style=s)
        for s in ["summary", "fact_only", "full_context"]
    }
    assert len(set(texts.values())) == 3
    assert "FACT:" not in texts["summary"] and "FACT:" in texts["fact_only"]
    with pytest.raises(ValueError, match="handoff_style"):
        render_system_prompt(cfg, "B", TEAM, handoff_style="loud")
