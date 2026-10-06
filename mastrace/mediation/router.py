"""Router: the only path for messages between agents (plan.md §7.2, P3.2).

The router owns the inboxes, checks every message against the graph config, records it as
a `message` or `router_reject` event, and decides when the run ends. It is the only
component that applies quarantine (I3).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from mastrace.core.ids import agent_actor
from mastrace.core.schemas import (
    DropMessageOverride,
    EventKind,
    EventRecord,
    GraphConfig,
    Override,
)
from mastrace.mediation.budget import TokenBudget
from mastrace.provenance.recorder import EventDraft, Recorder

RejectReason = Literal["no_link", "limit", "budget", "quarantined", "dropped"]
RunStatus = Literal[
    "completed", "stopped_superstep_limit", "stopped_budget", "stopped_idle", "crashed"
]


@dataclass(frozen=True)
class InboxItem:
    """Something delivered to an agent: a task or a message, tagged with its event ID."""

    event_id: str
    sender: str  # agent ID, or "user" for tasks
    content: str
    kind: Literal["task", "message"] = "message"


@dataclass(frozen=True)
class OutgoingMessage:
    """A message an agent asked to send, before the router checks it."""

    sender: str
    to: str
    content: str
    built_from: str  # the model_call that produced it (local ref or event ID)
    order: int  # position within the sender's turn


def _turn_of(ref: str) -> int | None:
    """Turn number of a `local:<agent>#<n>:<k>` reference (None for other refs)."""
    m = re.match(r"local:[A-Za-z0-9_]+#(\d+):", ref)
    return int(m.group(1)) if m else None


class Router:
    """Inboxes, link checks, per-direction limits, quarantine and termination."""

    def __init__(
        self,
        cfg: GraphConfig,
        recorder: Recorder,
        budget: TokenBudget,
        overrides: Sequence[Override] = (),
    ) -> None:
        self.cfg = cfg
        self.recorder = recorder
        self.budget = budget
        self.inboxes: dict[str, list[InboxItem]] = {a.id: [] for a in cfg.agents}
        self.accepted: dict[tuple[str, str], int] = {}
        self.attempts: dict[tuple[str, str], int] = {}
        self.quarantined: set[str] = set()
        self.quarantined_turns: set[tuple[str, int]] = set()
        self._drops = {
            (o.from_, o.to, o.nth) for o in overrides if isinstance(o, DropMessageOverride)
        }
        self._handled = 0

    # -- inboxes -----------------------------------------------------------------

    def put_task(self, agent_id: str, event_id: str, content: str) -> None:
        """Place a recorded `task_input` in an entry agent's inbox."""
        self.inboxes[agent_id].append(InboxItem(event_id, "user", content, kind="task"))

    def take_inbox(self, agent_id: str) -> list[InboxItem]:
        """Remove and return an agent's pending items."""
        items, self.inboxes[agent_id] = self.inboxes[agent_id], []
        return items

    def agents_with_mail(self) -> list[str]:
        """Agents with a non-empty inbox, sorted by ID."""
        return sorted(a for a, items in self.inboxes.items() if items)

    def has_pending(self) -> bool:
        """True if any inbox is non-empty."""
        return any(self.inboxes.values())

    # -- delivery ------------------------------------------------------------------

    def _check(self, m: OutgoingMessage, nth: int) -> RejectReason | None:
        if m.to not in self.inboxes or not self.cfg.allows(m.sender, m.to):
            return "no_link"
        if m.sender in self.quarantined or m.to in self.quarantined:
            return "quarantined"
        if (m.sender, _turn_of(m.built_from)) in self.quarantined_turns:
            return "quarantined"
        if (m.sender, m.to, nth) in self._drops:
            return "dropped"
        if self.accepted.get((m.sender, m.to), 0) >= self.cfg.limits.max_messages_per_direction:
            return "limit"
        if self.budget.exceeded:
            return "budget"
        return None

    def deliver(self, messages: Iterable[OutgoingMessage], superstep: int) -> list[EventRecord]:
        """Check, record and deliver messages in order (receiver, sender, order in turn)."""
        records = []
        for m in sorted(messages, key=lambda m: (m.to, m.sender, m.order)):
            direction = (m.sender, m.to)
            self.attempts[direction] = self.attempts.get(direction, 0) + 1
            reason = self._check(m, self.attempts[direction])
            self._handled += 1
            if reason is not None:
                records.append(
                    self.recorder.record_now(
                        EventDraft(
                            kind=EventKind.ROUTER_REJECT,
                            actor="router",
                            superstep=superstep,
                            receivers=[m.to],
                            built_from=[m.built_from],
                            output_text=m.content,
                            meta={"reason": reason, "from": m.sender, "to": m.to},
                        )
                    )
                )
                continue
            count = self.accepted.get(direction, 0) + 1
            self.accepted[direction] = count
            rec = self.recorder.record_now(
                EventDraft(
                    kind=EventKind.MESSAGE,
                    actor=agent_actor(m.sender),
                    superstep=superstep,
                    receivers=[m.to],
                    link={
                        "from": m.sender,
                        "to": m.to,
                        "type": self.cfg.link_type(m.sender, m.to),
                        "count": count,
                    },
                    built_from=[m.built_from],
                    output_text=m.content,
                )
            )
            self.inboxes[m.to].append(InboxItem(rec.event_id, m.sender, m.content))
            records.append(rec)
        return records

    # -- quarantine --------------------------------------------------------------

    def quarantine(
        self, agent_id: str, superstep: int, symptom_event_id: str, verdict_id: str
    ) -> EventRecord:
        """Quarantine an agent: its messages in and out are rejected from now on."""
        self.quarantined.add(agent_id)
        return self.recorder.record_now(
            EventDraft(
                kind=EventKind.QUARANTINE,
                actor="router",
                superstep=superstep,
                receivers=[agent_id],
                built_from=[symptom_event_id],
                meta={"verdict_id": verdict_id, "agent": agent_id},
            )
        )

    def quarantine_turn(
        self, agent_id: str, turn: int, superstep: int, verdict_id: str, symptom_event_id: str
    ) -> EventRecord:
        """Quarantine one turn of an agent (P12.2): its outgoing messages are rejected.

        Tool revocation for the same turn is applied by the tool gateway. The symptom lives
        in the original run, so it is referenced in `meta`, not `built_from`.
        """
        self.quarantined_turns.add((agent_id, turn))
        return self.recorder.record_now(
            EventDraft(
                kind=EventKind.QUARANTINE,
                actor="router",
                superstep=superstep,
                receivers=[agent_id],
                meta={
                    "agent": agent_id,
                    "turn": turn,
                    "verdict_id": verdict_id,
                    "symptom_event_id": symptom_event_id,
                    "scope": "turn",
                },
            )
        )

    # -- termination ---------------------------------------------------------------

    def decide(self, superstep: int, sink_has_output: bool) -> RunStatus | None:
        """Return the final status, or None to run another superstep (§7.2 rule 4)."""
        pending = self.has_pending()
        if sink_has_output and not pending:
            return "completed"
        if self.budget.exceeded:
            return "stopped_budget"
        if superstep >= self.cfg.limits.max_supersteps:
            return "stopped_superstep_limit"
        if not pending:
            return "stopped_idle"
        return None

    def stats(self) -> dict[str, int]:
        """Counters for gate check G-C1 (`messages` == message + router_reject events)."""
        return {"messages": self._handled}
