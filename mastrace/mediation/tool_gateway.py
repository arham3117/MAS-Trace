"""Tool gateway: the only path from an agent to a tool (plan.md §7.8, P2.3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mastrace.core.canonical import canonical_json, request_hash_tool
from mastrace.core.ids import parse_turn_id
from mastrace.core.schemas import EventKind, Override, ToolOutputOverride, ToolResult
from mastrace.mediation.cache import ResponseCache
from mastrace.mediation.memory import MemoryService
from mastrace.mediation.tools import REGISTRY, Tool, ToolContext
from mastrace.provenance.recorder import EventBuffer


@dataclass(frozen=True)
class ToolCallResult:
    """What an agent gets back: the result plus the local ref of the tool event."""

    result: ToolResult
    event_ref: str


class ToolGateway:
    """Checks grants and arguments, applies overrides, caches, and records tool calls."""

    def __init__(
        self,
        env_dir: Path,
        env_snapshot_hash: str,
        grants: Mapping[str, Sequence[str]],
        cache: ResponseCache | None = None,
        overrides: Sequence[Override] = (),
        memory: MemoryService | None = None,
        registry: Mapping[str, Tool] = REGISTRY,
    ) -> None:
        self.env_dir = env_dir
        self.env_snapshot_hash = env_snapshot_hash
        self.grants = {a: set(ts) for a, ts in grants.items()}
        self.cache = cache
        self.memory = memory or MemoryService()
        self.registry = registry
        self._overrides = {
            (o.agent, o.turn, o.call_index): o
            for o in overrides
            if isinstance(o, ToolOutputOverride)
        }
        self._calls = 0
        self.revoked_turns: set[tuple[str, int]] = set()

    def stats(self) -> dict[str, int]:
        """Counters for gate check G-C1 (`calls` == number of tool events)."""
        return {"calls": self._calls}

    def revoke_turn(self, agent_id: str, turn: int) -> None:
        """Deny every tool call of one agent turn (quarantine, P12.2)."""
        self.revoked_turns.add((agent_id, turn))

    def revoke(self, agent_id: str) -> None:
        """Remove every tool grant of an agent (used by quarantine, Phase 12)."""
        self.grants[agent_id] = set()

    def _check_args(self, tool: Tool, args: Mapping[str, Any]) -> str | None:
        missing = [a for a in tool.args if a not in args]
        extra = sorted(set(args) - set(tool.args))
        if missing or extra:
            return f"Invalid arguments for {tool.name}: missing {missing}, unexpected {extra}"
        bad = [a for a in tool.args if not isinstance(args[a], str)]
        if bad:
            return f"Invalid arguments for {tool.name}: {bad} must be strings"
        return None

    def call(
        self,
        agent_id: str,
        turn_id: str,
        call_index: int,
        tool_name: str,
        args: Mapping[str, Any],
        built_from: Sequence[str],
        buffer: EventBuffer,
    ) -> ToolCallResult:
        """Run one tool call for an agent and buffer its event."""
        args = dict(args)
        tool = self.registry.get(tool_name)
        rhash = request_hash_tool(tool_name, args, self.env_snapshot_hash)
        meta: dict[str, Any] = {
            "tool": tool_name,
            "args": args,
            "source": tool.source if tool else None,
            "cache_hit": False,
        }
        _, turn_n = parse_turn_id(turn_id)
        override = self._overrides.get((agent_id, turn_n, call_index))

        if tool is None:
            result = ToolResult(output=f"Unknown tool: {tool_name}", status="denied")
        elif (agent_id, turn_n) in self.revoked_turns:
            result = ToolResult(
                output=f"Tool '{tool_name}' is not available: agent {agent_id} is quarantined.",
                status="denied",
            )
            meta["quarantined"] = True
        elif tool_name not in self.grants.get(agent_id, set()):
            result = ToolResult(
                output=f"Tool '{tool_name}' is not available to agent {agent_id}.",
                status="denied",
            )
        elif (err := self._check_args(tool, args)) is not None:
            result = ToolResult(output=err, status="error")
        elif override is not None:
            result = ToolResult(output=override.replacement)
            meta["override"] = True
        else:
            cached = self.cache.get_tool(rhash) if (tool.cacheable and self.cache) else None
            if cached is not None:
                result = cached
                meta["cache_hit"] = True
            else:
                ctx = ToolContext(env_dir=self.env_dir, agent_id=agent_id, memory=self.memory)
                result = tool.run(ctx, args)
                if tool.cacheable and self.cache:
                    self.cache.put_tool(rhash, tool_name, result)
        meta["status"] = result.status
        ref = buffer.add(
            tool.event_kind if tool else EventKind.TOOL_CALL,
            call_index=call_index,
            built_from=list(built_from),
            request_hash=rhash,
            input_text=canonical_json({"tool": tool_name, "args": args}),
            output_text=result.output,
            meta=meta,
        )
        self._calls += 1
        return ToolCallResult(result=result, event_ref=ref)
