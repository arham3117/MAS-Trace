"""Pydantic schemas shared by every layer (plan.md §7)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AgentId = str
LinkType = Literal["one_way", "two_way"]


class _Model(BaseModel):
    """Base for all schemas: unknown fields are errors, aliases serialize by alias."""

    model_config = ConfigDict(extra="forbid", validate_by_name=True, serialize_by_alias=True)


# --------------------------------------------------------------------------- events (§7.4)


class EventKind(StrEnum):
    """Every kind of recorded action."""

    RUN_START = "run_start"
    RUN_END = "run_end"
    TASK_INPUT = "task_input"
    MESSAGE = "message"
    ROUTER_REJECT = "router_reject"
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    EXTERNAL_READ = "external_read"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    FINAL_OUTPUT = "final_output"
    QUARANTINE = "quarantine"


class EventRecord(_Model):
    """One committed, hash-chained and signed event."""

    event_id: str
    run_id: str
    seq: int
    stage: int
    code_version: str
    time: str
    superstep: int
    kind: EventKind
    actor: str
    turn_id: str | None = None
    call_index: int | None = None
    receivers: list[str] = Field(default_factory=list)
    link: dict[str, Any] | None = None
    built_from: list[str] = Field(default_factory=list)
    request_hash: str | None = None
    input_ref: str | None = None
    output_ref: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    record_hash: str
    signature: str

    def hashable_dict(self) -> dict[str, Any]:
        """The record as JSON-ready data, without `record_hash` and `signature` (§7.6)."""
        return self.model_dump(mode="json", exclude={"record_hash", "signature"})


# --------------------------------------------------------------------------- overrides (§7.7)


class ToolOutputOverride(_Model):
    """Replace the output of one tool call (also used to neutralize memory reads)."""

    kind: Literal["tool_output"] = "tool_output"
    agent: AgentId
    turn: int
    call_index: int
    replacement: str


class ModelOutputOverride(_Model):
    """Replace the text returned by one model call."""

    kind: Literal["model_output"] = "model_output"
    agent: AgentId
    turn: int
    call_index: int
    replacement: str


class DropMessageOverride(_Model):
    """Make the router drop the n-th message (1-based) sent from one agent to another."""

    kind: Literal["drop_message"] = "drop_message"
    from_: AgentId = Field(alias="from")
    to: AgentId
    nth: int = Field(ge=1)


Override = Annotated[
    ToolOutputOverride | ModelOutputOverride | DropMessageOverride, Field(discriminator="kind")
]


# --------------------------------------------------------------------------- run records


class RunManifest(_Model):
    """Contents of `data/runs/<run_id>/manifest.json` (§7.5)."""

    run_id: str
    config_name: str
    config_hash: str
    config: dict[str, Any]
    stage: int
    task_id: str
    attack_id: str | None
    model_key: str
    seed: int
    mode: Literal["record", "replay", "strict_replay"] = "record"
    overrides: list[Override] = Field(default_factory=list)
    code_version: str
    status: str = "created"
    env_snapshot_hash: str | None = None
    replay_of: str | None = None


class Alert(_Model):
    """One detector hit (§7.10)."""

    detector: str
    severity: Literal["low", "medium", "high"]
    event_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class GroundTruth(_Model):
    """What the injector actually did. Lives only in `ground_truth.sqlite` (§7.9, I8)."""

    run_id: str
    attack_id: str
    goal: Literal["G1", "G2"] | None
    stealth: Literal["S0", "S1", "S2", "S3"] | None
    target_agent: AgentId
    target_url: str
    poisoned_page_sha256: str
    kind: Literal["attack", "honest_error"] = "attack"


class InjectionInfo(_Model):
    """The only part of an injection the controller sees."""

    run_id: str
    injected: bool


class Verdict(_Model):
    """The tracer's answer for one symptom (§7.12)."""

    verdict_id: str
    run_id: str
    method: str
    symptom_event_id: str
    status: Literal["confirmed", "unconfirmed", "no_symptom"]
    entry_event_id: str | None = None
    entry_agent: AgentId | None = None
    entry_turn: str | None = None
    confirmed_entry_events: list[str] = Field(default_factory=list)
    paths: list[list[AgentId]] = Field(default_factory=list)
    ranking: list[dict[str, Any]] = Field(default_factory=list)
    replays: list[dict[str, Any]] = Field(default_factory=list)
    tokens_used: int = 0
    replays_used: int = 0


# --------------------------------------------------------------------------- graph config (§7.1)


class AgentSpec(_Model):
    """One agent in a graph config."""

    id: AgentId
    role: str
    tools: list[str] = Field(default_factory=list)


class LinkSpec(_Model):
    """An allowed message direction (`one_way`) or pair of directions (`two_way`)."""

    from_: AgentId = Field(alias="from")
    to: AgentId
    type: LinkType

    def directions(self) -> list[tuple[AgentId, AgentId]]:
        """The (sender, receiver) pairs this link allows."""
        if self.type == "two_way":
            return [(self.from_, self.to), (self.to, self.from_)]
        return [(self.from_, self.to)]


class Limits(_Model):
    """Per-run limits enforced by the router and agent runner."""

    max_messages_per_direction: int = Field(default=3, ge=1)
    max_supersteps: int = Field(default=20, ge=1)
    max_tool_calls_per_turn: int = Field(default=4, ge=0)
    max_tokens_run: int = Field(default=60000, ge=1)


REQUIRED_AGENT_COUNT = 5


class GraphConfig(_Model):
    """A 5-agent graph with typed links. Validators implement §7.1 rules 1-6.

    Rule 7 (prompt files and tool registry) needs the filesystem and the registry, so it is
    `check_resources`; rule 8 depends on the provider, so it is `check_scripted_feedback`.
    """

    name: str
    stage: Literal[1, 2, 3]
    description: str = ""
    agents: list[AgentSpec]
    links: list[LinkSpec]
    entry_agents: list[AgentId] = Field(min_length=1)
    sink_agent: AgentId
    limits: Limits = Field(default_factory=Limits)
    model: str

    @model_validator(mode="after")
    def _validate(self) -> GraphConfig:
        self._rule1_agents()
        self._rule2_links()
        self._rule3_reachable()
        self._rules456_stage()
        return self

    def _rule1_agents(self) -> None:
        ids = [a.id for a in self.agents]
        if len(ids) != REQUIRED_AGENT_COUNT:
            raise ValueError(
                f"rule 1: exactly {REQUIRED_AGENT_COUNT} agents required, got {len(ids)}"
            )
        if len(set(ids)) != len(ids):
            raise ValueError(f"rule 1: agent IDs must be unique, got {ids}")

    def _rule2_links(self) -> None:
        known = {a.id for a in self.agents}
        pair_types: dict[frozenset[str], set[str]] = {}
        for link in self.links:
            for end in (link.from_, link.to):
                if end not in known:
                    raise ValueError(f"rule 2: link references unknown agent {end!r}")
            if link.from_ == link.to:
                raise ValueError(f"rule 2: self link on {link.from_!r}")
            pair_types.setdefault(frozenset((link.from_, link.to)), set()).add(link.type)
        for pair, types in sorted(pair_types.items(), key=lambda kv: sorted(kv[0])):
            if len(types) > 1:
                raise ValueError(f"rule 2: pair {sorted(pair)} declared both one_way and two_way")
        seen_dirs: set[tuple[str, str]] = set()
        for link in self.links:
            for d in link.directions():
                if d in seen_dirs:
                    raise ValueError(f"rule 2: duplicate link {d[0]}->{d[1]}")
                seen_dirs.add(d)
        for a in [*self.entry_agents, self.sink_agent]:
            if a not in known:
                raise ValueError(f"rule 2: entry/sink agent {a!r} is not a known agent")

    def _rule3_reachable(self) -> None:
        for entry in self.entry_agents:
            if self.sink_agent not in self.reachable_from(entry):
                raise ValueError(f"rule 3: sink {self.sink_agent!r} not reachable from {entry!r}")

    def _rules456_stage(self) -> None:
        types = {link.type for link in self.links}
        if self.stage == 1:
            if types - {"one_way"}:
                raise ValueError("rule 4: stage 1 allows only one_way links")
            if not self._is_dag():
                raise ValueError("rule 4: stage 1 graph must be a DAG")
        elif self.stage == 2:
            if types - {"two_way"}:
                raise ValueError("rule 5: stage 2 allows only two_way links")
        elif types != {"one_way", "two_way"}:
            raise ValueError("rule 6: stage 3 needs at least one link of each type")

    # -- graph helpers ------------------------------------------------------

    def directed_edges(self) -> list[tuple[AgentId, AgentId]]:
        """Every allowed (sender, receiver) direction, sorted."""
        return sorted(d for link in self.links for d in link.directions())

    def allows(self, sender: AgentId, receiver: AgentId) -> bool:
        """True if a message from `sender` to `receiver` is allowed by some link."""
        return (sender, receiver) in self.directed_edges()

    def out_neighbours(self, agent: AgentId) -> list[AgentId]:
        """Agents that `agent` may send to, sorted."""
        return sorted({r for s, r in self.directed_edges() if s == agent})

    def in_neighbours(self, agent: AgentId) -> list[AgentId]:
        """Agents that may send to `agent`, sorted."""
        return sorted({s for s, r in self.directed_edges() if r == agent})

    def link_type(self, a: AgentId, b: AgentId) -> LinkType | None:
        """The type of the link between `a` and `b` in either direction, if any."""
        for link in self.links:
            if {link.from_, link.to} == {a, b}:
                return link.type
        return None

    def agent(self, agent_id: AgentId) -> AgentSpec:
        """Look up an agent by ID."""
        for a in self.agents:
            if a.id == agent_id:
                return a
        raise KeyError(agent_id)

    def reachable_from(self, start: AgentId) -> set[AgentId]:
        """Agents reachable from `start` along allowed directions (including `start`)."""
        seen = {start}
        frontier = [start]
        while frontier:
            node = frontier.pop()
            for nxt in self.out_neighbours(node):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        return seen

    def _is_dag(self) -> bool:
        indeg = {a.id: 0 for a in self.agents}
        for _, r in self.directed_edges():
            indeg[r] += 1
        ready = sorted(a for a, d in indeg.items() if d == 0)
        visited = 0
        while ready:
            node = ready.pop()
            visited += 1
            for nxt in self.out_neighbours(node):
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready.append(nxt)
        return visited == len(indeg)

    # -- rules that need outside context -----------------------------------

    def check_resources(self, prompts_dir: Path, tool_names: set[str]) -> None:
        """Rule 7: every role has `<prompts_dir>/<role>.md` and every tool is registered."""
        for a in self.agents:
            if not (prompts_dir / f"{a.role}.md").is_file():
                raise ValueError(f"rule 7: no prompt file for role {a.role!r} (agent {a.id})")
            for tool in a.tools:
                if tool not in tool_names:
                    raise ValueError(f"rule 7: unknown tool {tool!r} on agent {a.id}")

    def check_scripted_feedback(self, feedback_rounds: int) -> None:
        """Rule 8: with the scripted provider, feedback rounds must fit the message limit."""
        if feedback_rounds > self.limits.max_messages_per_direction:
            raise ValueError(
                f"rule 8: feedback_rounds={feedback_rounds} exceeds "
                f"max_messages_per_direction={self.limits.max_messages_per_direction}"
            )


# --------------------------------------------------------------------------- tasks and attacks


class TaskSpec(_Model):
    """`env/templates/tNN/task.yaml` (§7.8)."""

    id: str
    instruction: str
    sources: list[str] = Field(min_length=1)
    sources_2: list[str] = Field(default_factory=list)
    expected_facts: list[str]
    allowed_recipients: list[str] = Field(min_length=1)
    notes: str = ""

    @field_validator("expected_facts")
    @classmethod
    def _three_facts(cls, v: list[str]) -> list[str]:
        if len(v) != 3:
            raise ValueError(f"expected exactly 3 expected_facts, got {len(v)}")
        return v


class AttackSpec(_Model):
    """`attacks/<id>.yaml` (§7.9)."""

    id: str
    goal: Literal["G1", "G2"]
    stealth: Literal["S0", "S1", "S2", "S3"]
    enabled_from_phase: int
    placement: Literal["append", "middle"] = "append"
    template: str
    params: dict[str, str | None] = Field(default_factory=dict)

    @field_validator("template")
    @classmethod
    def _single_paragraph(cls, v: str) -> str:
        lines = v.strip().splitlines()
        if any(not line.strip() for line in lines):
            raise ValueError("template must be a single paragraph with no blank lines")
        return v

    @model_validator(mode="after")
    def _g2_has_marker(self) -> AttackSpec:
        if self.goal == "G2" and "MARKER:" not in self.template:
            raise ValueError("G2 templates must contain 'MARKER: {marker}'")
        return self


# --------------------------------------------------------------------------- gateway I/O


class ChatMessage(_Model):
    """One prompt item sent to a model."""

    role: Literal["system", "user", "assistant"]
    content: str


class ModelRequest(_Model):
    """A model call as seen by providers."""

    model: str
    messages: list[ChatMessage]
    temperature: float = 0.0
    max_tokens: int = 1024
    seed: int | None = None


class ModelResponse(_Model):
    """A provider's answer plus token accounting."""

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Prompt plus completion tokens."""
        return self.prompt_tokens + self.completion_tokens


class ToolRequest(_Model):
    """A tool call as requested by an agent."""

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResult(_Model):
    """The result of a tool call, as returned to the agent."""

    output: str
    status: Literal["ok", "denied", "error"] = "ok"
