"""P6.1: EventGraph on synthetic logs."""

from __future__ import annotations

from mastrace.core.schemas import EventKind, EventRecord
from mastrace.provenance.event_graph import EventGraph


def ev(
    seq: int,
    kind: EventKind,
    actor: str,
    built_from: list[int],
    turn: str | None = None,
    receivers: list[str] | None = None,
) -> EventRecord:
    return EventRecord(
        event_id=f"r:{seq:06d}",
        run_id="r",
        seq=seq,
        stage=2,
        code_version="x",
        time="t",
        superstep=0,
        kind=kind,
        actor=actor,
        turn_id=turn,
        receivers=receivers or [],
        built_from=[f"r:{b:06d}" for b in built_from],
        prev_hash="p",
        record_hash="h",
        signature="s",
    )


M, X, MSG = EventKind.MODEL_CALL, EventKind.EXTERNAL_READ, EventKind.MESSAGE


def two_way_log() -> list[EventRecord]:
    """A reads a page, talks to B; B and A go back and forth; B messages C (the symptom)."""
    return [
        ev(1, EventKind.TASK_INPUT, "user", []),
        ev(2, M, "agent:A", [1], "A#1"),
        ev(3, X, "agent:A", [2], "A#1"),
        ev(4, M, "agent:A", [1, 2, 3], "A#1"),
        ev(5, MSG, "agent:A", [4], receivers=["B"]),
        ev(6, M, "agent:B", [5], "B#1"),
        ev(7, MSG, "agent:B", [6], receivers=["A"]),
        ev(8, M, "agent:A", [1, 2, 3, 4, 7], "A#2"),
        ev(9, MSG, "agent:A", [8], receivers=["B"]),
        ev(10, M, "agent:B", [5, 6, 9], "B#2"),
        ev(11, MSG, "agent:B", [10], receivers=["C"]),
        ev(12, M, "agent:C", [11], "C#1"),
        ev(13, EventKind.TOOL_CALL, "agent:C", [12], "C#1"),
    ]


def test_acyclic_and_ancestors_with_depth() -> None:
    g = EventGraph(two_way_log())
    assert g.is_acyclic()
    anc = g.ancestors("r:000013")
    assert anc["r:000012"] == 1 and anc["r:000003"] >= 4
    assert "r:000001" in anc and "r:000013" not in anc


def test_each_node_visited_once_in_diamonds() -> None:
    g = EventGraph(two_way_log())
    g.ancestors("r:000013")
    assert max(g.visits.values()) == 1
    assert len(g.visits) == 13


def test_simple_paths_through_conversation() -> None:
    g = EventGraph(two_way_log())
    assert g.simple_paths("A#1", "r:000013") == [["A", "B", "C"]]


def test_descendants() -> None:
    g = EventGraph(two_way_log())
    assert "r:000013" in g.descendants("r:000003")
    assert "r:000003" not in g.descendants("r:000005")


def test_long_back_and_forth_stays_acyclic() -> None:
    events = [ev(1, EventKind.TASK_INPUT, "user", [])]
    seq, last = 2, 1
    for i in range(30):
        a = "A" if i % 2 == 0 else "B"
        events.append(ev(seq, M, f"agent:{a}", [last], f"{a}#{i // 2 + 1}"))
        events.append(ev(seq + 1, MSG, f"agent:{a}", [seq], receivers=["B" if a == "A" else "A"]))
        last, seq = seq + 1, seq + 2
    g = EventGraph(events)
    assert g.is_acyclic()
    g.ancestors(events[-1].event_id)
    assert max(g.visits.values()) == 1


# -- ISSUE-024 general rule: consequences are not entry points ------------------------------


def test_select_entries_drops_same_agent_consequence() -> None:
    """A reads a page, then (because of it) reads internal/policy.md in the same turn."""
    from mastrace.analysis.tracer import select_entries

    events = [
        ev(1, EventKind.TASK_INPUT, "user", []),
        ev(2, M, "agent:A", [1], "A#1"),
        ev(3, X, "agent:A", [2], "A#1"),  # poisoned page
        ev(4, M, "agent:A", [1, 2, 3], "A#1"),
        ev(5, EventKind.TOOL_CALL, "agent:A", [4], "A#1"),  # read_file internal/policy.md
        ev(6, M, "agent:A", [1, 2, 3, 4, 5], "A#1"),
    ]
    g = EventGraph(events)
    assert select_entries(g, ["r:000005", "r:000003"]) == ["r:000003"]
    assert select_entries(g, ["r:000003"]) == ["r:000003"]


def test_select_entries_drops_downstream_memory_read() -> None:
    from mastrace.analysis.tracer import select_entries

    events = [
        ev(1, EventKind.TASK_INPUT, "user", []),
        ev(2, M, "agent:A", [1], "A#1"),
        ev(3, X, "agent:A", [2], "A#1"),
        ev(4, M, "agent:A", [1, 2, 3], "A#1"),
        ev(5, MSG, "agent:A", [4], receivers=["B"]),
        ev(6, M, "agent:B", [5], "B#1"),
        ev(7, EventKind.MEMORY_READ, "agent:B", [6], "B#1"),
        ev(8, X, "agent:B", [6], "B#1"),
    ]
    g = EventGraph(events)
    # B's memory read descends from A's page: a consequence. Independent entries survive.
    assert select_entries(g, ["r:000007", "r:000003"]) == ["r:000003"]
    independent = EventGraph([*events[:4], ev(9, X, "agent:B", [1], "B#1")])
    assert select_entries(independent, ["r:000003", "r:000009"]) == ["r:000003", "r:000009"]
