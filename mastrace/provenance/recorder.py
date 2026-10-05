"""Recorder: turns buffered drafts into hash-chained, signed events (plan.md §7.4-7.6, P1.6).

Events produced inside an agent turn are collected in an `EventBuffer` and committed by the
router at the end of the superstep. Event IDs depend on commit order, so while buffered an
event is named by a local reference (`local:<turn_id>:<k>`). Other drafts may list local
references in `built_from`; the recorder rewrites them to real event IDs at commit, and keeps
the mapping so later events (e.g. router `message` events) can still use them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mastrace.core.canonical import canonical_json, sha256_hex
from mastrace.core.errors import MastraceError, UnknownLocalRef
from mastrace.core.ids import agent_actor, event_id, parse_turn_id
from mastrace.core.schemas import EventKind, EventRecord
from mastrace.provenance.event_store import EventStore
from mastrace.provenance.payload_store import PayloadStore
from mastrace.provenance.signer import Signer

GENESIS = "GENESIS"
LOCAL_PREFIX = "local:"


def utc_now_iso() -> str:
    """Current UTC time in ISO-8601 (informational only)."""
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def compute_record_hash(hashable: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON of a record without `record_hash`/`signature`."""
    return sha256_hex(canonical_json(hashable))


class EventDraft(BaseModel):
    """An event before it has a `seq`, an ID, payload refs, hashes and a signature."""

    model_config = ConfigDict(extra="forbid")

    kind: EventKind
    actor: str
    superstep: int
    turn_id: str | None = None
    call_index: int | None = None
    receivers: list[str] = Field(default_factory=list)
    link: dict[str, Any] | None = None
    built_from: list[str] = Field(default_factory=list)
    request_hash: str | None = None
    input_text: str | None = None
    output_text: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


@dataclass
class EventBuffer:
    """Pending events of one agent turn, in the order they happened."""

    agent_id: str
    turn_id: str
    superstep: int
    drafts: list[EventDraft] = field(default_factory=list)

    def add(self, kind: EventKind, **fields: Any) -> str:
        """Buffer an event of this turn and return its local reference."""
        fields.setdefault("actor", agent_actor(self.agent_id))
        draft = EventDraft(kind=kind, superstep=self.superstep, turn_id=self.turn_id, **fields)
        self.drafts.append(draft)
        return self.local_ref(len(self.drafts) - 1)

    def local_ref(self, index: int) -> str:
        """Local reference of the draft at `index`."""
        return f"{LOCAL_PREFIX}{self.turn_id}:{index}"

    def sort_key(self) -> tuple[str, int]:
        """Commit order: by agent ID, then turn number."""
        return parse_turn_id(self.turn_id)


@dataclass(frozen=True)
class CommitResult:
    """What a commit produced."""

    records: list[EventRecord]
    id_map: dict[str, str]


class Recorder:
    """The only writer of a run's event log."""

    def __init__(
        self,
        run_id: str,
        stage: int,
        store: EventStore,
        payloads: PayloadStore,
        signer: Signer,
        code_version: str,
        clock: Callable[[], str] = utc_now_iso,
    ) -> None:
        self.run_id = run_id
        self.stage = stage
        self.store = store
        self.payloads = payloads
        self.signer = signer
        self.code_version = code_version
        self.clock = clock
        last = store.last()
        self._next_seq = 1 if last is None else last.seq + 1
        self._prev_hash = GENESIS if last is None else last.record_hash
        self._local_ids: dict[str, str] = {}

    # -- public API ------------------------------------------------------------

    def commit(self, buffers: Iterable[EventBuffer]) -> CommitResult:
        """Commit turn buffers in deterministic order (agent ID, turn, order within turn)."""
        ordered = sorted(buffers, key=lambda b: b.sort_key())
        keys = [b.turn_id for b in ordered]
        if len(set(keys)) != len(keys):
            raise MastraceError(f"duplicate turn buffers in one commit: {keys}")
        id_map: dict[str, str] = {}
        records: list[EventRecord] = []
        saved = (self._next_seq, self._prev_hash)
        try:
            for buf in ordered:
                for i, draft in enumerate(buf.drafts):
                    rec = self._build(draft, extra_ids=id_map)
                    id_map[buf.local_ref(i)] = rec.event_id
                    records.append(rec)
            self.store.append_many(records)
        except BaseException:
            self._next_seq, self._prev_hash = saved
            raise
        self._local_ids.update(id_map)
        return CommitResult(records=records, id_map=id_map)

    def record_now(self, draft: EventDraft) -> EventRecord:
        """Record a router or controller event immediately."""
        saved = (self._next_seq, self._prev_hash)
        try:
            rec = self._build(draft, extra_ids={})
            self.store.append(rec)
        except BaseException:
            self._next_seq, self._prev_hash = saved
            raise
        return rec

    def resolve(self, ref: str) -> str:
        """Map a local reference to its committed event ID (event IDs pass through)."""
        if not ref.startswith(LOCAL_PREFIX):
            return ref
        try:
            return self._local_ids[ref]
        except KeyError as e:
            raise UnknownLocalRef(ref) from e

    # -- internals ---------------------------------------------------------------

    def _build(self, draft: EventDraft, extra_ids: dict[str, str]) -> EventRecord:
        built_from = []
        for ref in draft.built_from:
            if ref.startswith(LOCAL_PREFIX) and ref in extra_ids:
                built_from.append(extra_ids[ref])
            else:
                built_from.append(self.resolve(ref))
        seq = self._next_seq
        fields: dict[str, Any] = {
            "event_id": event_id(self.run_id, seq),
            "run_id": self.run_id,
            "seq": seq,
            "stage": self.stage,
            "code_version": self.code_version,
            "time": self.clock(),
            "superstep": draft.superstep,
            "kind": draft.kind,
            "actor": draft.actor,
            "turn_id": draft.turn_id,
            "call_index": draft.call_index,
            "receivers": list(draft.receivers),
            "link": draft.link,
            "built_from": built_from,
            "request_hash": draft.request_hash,
            "input_ref": None if draft.input_text is None else self.payloads.put(draft.input_text),
            "output_ref": (
                None if draft.output_text is None else self.payloads.put(draft.output_text)
            ),
            "meta": dict(draft.meta),
            "prev_hash": self._prev_hash,
        }
        unsigned = EventRecord(**fields, record_hash="", signature="")
        record_hash = compute_record_hash(unsigned.hashable_dict())
        rec = unsigned.model_copy(
            update={"record_hash": record_hash, "signature": self.signer.sign(record_hash)}
        )
        self._next_seq += 1
        self._prev_hash = record_hash
        return rec
