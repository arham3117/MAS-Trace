"""Tool definitions shared by the registry and the tool gateway (plan.md §7.8)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from mastrace.core.schemas import EventKind, ToolResult
from mastrace.mediation.memory import MemoryService

ToolSource = Literal["external", "internal", "action"]


@dataclass(frozen=True)
class ToolContext:
    """What a tool may touch: the run's materialized `env/` and the memory service."""

    env_dir: Path
    agent_id: str
    memory: MemoryService


@dataclass(frozen=True)
class Tool:
    """One registered tool."""

    name: str
    source: ToolSource
    event_kind: EventKind
    args: tuple[str, ...]
    run: Callable[[ToolContext, dict[str, Any]], ToolResult]
    description: str
    cacheable: bool = False  # deterministic given the env snapshot and free of side effects
