"""Deterministic, counter-based identifiers (plan.md §7.5, §7.7)."""

from __future__ import annotations

import re

from mastrace.core.canonical import canonical_json, sha256_hex

_TURN = re.compile(r"([A-Za-z0-9_]+)#([0-9]+)")


def event_id(run_id: str, seq: int) -> str:
    """`<run_id>:<seq:06d>`."""
    return f"{run_id}:{seq:06d}"


def turn_id(agent_id: str, n: int) -> str:
    """`<agent>#<n>`, e.g. `A#1` (turns are numbered from 1)."""
    return f"{agent_id}#{n}"


def parse_turn_id(tid: str) -> tuple[str, int]:
    """Split `A#3` into `("A", 3)`."""
    m = _TURN.fullmatch(tid)
    if m is None:
        raise ValueError(f"bad turn id: {tid!r}")
    return m.group(1), int(m.group(2))


def agent_actor(agent_id: str) -> str:
    """Actor string for an agent: `agent:<id>`."""
    return f"agent:{agent_id}"


def run_uid(
    config_hash: str,
    task_id: str,
    attack_id: str | None,
    model_key: str,
    seed: int,
    handoff_style: str,
    page_render: str,
) -> str:
    """Opaque run identifier used inside events (answers.md D4): `r_` + 16 hex chars."""
    t = {
        "config": config_hash,
        "task": task_id,
        "attack": attack_id or "clean",
        "model": model_key,
        "seed": seed,
        "handoff_style": handoff_style,
        "page_render": page_render,
    }
    return "r_" + sha256_hex(canonical_json(t))[:16]


def replay_uid(original_uid: str, k: int) -> str:
    """Opaque identifier of the k-th replay of a run."""
    return "r_" + sha256_hex(f"{original_uid}:r{k}")[:16]
