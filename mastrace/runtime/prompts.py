"""System prompts: role template + action protocol + agent profile (plan.md §7.8, P4.2)."""

from __future__ import annotations

from pathlib import Path

from mastrace.core.protocol import AgentProfile, render_profile
from mastrace.core.schemas import GraphConfig
from mastrace.mediation.tools import REGISTRY
from mastrace.settings import REPO_ROOT

PROMPTS_DIR = REPO_ROOT / "prompts"
TWO_WAY_LINE = "You may reply to an agent that messaged you to ask questions or give feedback."


def profile_for(cfg: GraphConfig, agent_id: str, allowed_recipients: list[str]) -> AgentProfile:
    """The agent's profile, derived from the graph config."""
    agent = cfg.agent(agent_id)
    outs = cfg.out_neighbours(agent_id)
    return AgentProfile(
        agent_id=agent_id,
        role=agent.role,
        out_neighbours=outs,
        two_way_with=[n for n in outs if cfg.link_type(agent_id, n) == "two_way"],
        tools=sorted(agent.tools),
        is_sink=agent_id == cfg.sink_agent,
        allowed_recipients=list(allowed_recipients),
    )


def _tool_list(tools: list[str]) -> str:
    if not tools:
        return "- none"
    lines = []
    for name in tools:
        t = REGISTRY[name]
        lines.append(f"- {name}({', '.join(t.args)}): {t.description}")
    return "\n".join(lines)


def _fill(template: str, values: dict[str, str]) -> str:
    # Plain replacement (not str.format) so JSON braces in templates need no escaping.
    for k, v in values.items():
        template = template.replace("{" + k + "}", v)
    return template


def render_system_prompt(
    cfg: GraphConfig,
    agent_id: str,
    allowed_recipients: list[str],
    prompts_dir: Path = PROMPTS_DIR,
) -> str:
    """Render the full system prompt for one agent."""
    p = profile_for(cfg, agent_id, allowed_recipients)
    values = {
        "agent_id": agent_id,
        "neighbours": ", ".join(p.out_neighbours) or "nobody (your turn ends without messages)",
        "tools": ", ".join(p.tools) or "none",
        "allowed_recipients": ", ".join(p.allowed_recipients),
        "is_sink": "you are" if p.is_sink else "you are not",
        "max_tool_calls": str(cfg.limits.max_tool_calls_per_turn),
        "two_way_line": TWO_WAY_LINE if p.two_way_with else "",
        "tool_list": _tool_list(p.tools),
    }
    role = _fill((prompts_dir / "roles" / f"{p.role}.md").read_text(encoding="utf-8"), values)
    protocol = _fill((prompts_dir / "protocol.md").read_text(encoding="utf-8"), values)
    return "\n\n".join([role.strip(), protocol.strip(), render_profile(p)])
