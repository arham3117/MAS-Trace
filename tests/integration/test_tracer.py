"""P7.2: tracer v1 on scripted runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from mastrace.analysis.tracer import Tracer, jaccard, ngrams
from mastrace.control.controller import run_with_attack
from mastrace.core.schemas import GroundTruth
from mastrace.evaluation.symptom_oracle import make_symptom_check, symptom_event
from mastrace.groundtruth.store import GroundTruthStore
from mastrace.provenance.event_store import EventStore
from mastrace.runtime.run import RunResult
from mastrace.settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def setup(
    settings: Settings, config: str = "s1_chain", attack: str = "g1s0", **kw: object
) -> tuple[RunResult, GroundTruth, str]:
    r = run_with_attack(config, "t01", attack, "scripted_gullible", 1, settings=settings, **kw)  # type: ignore[arg-type]
    with GroundTruthStore(settings.ground_truth_path) as s:
        gt = s.get(r.run_id)
    assert gt is not None
    sid = symptom_event(r.run_dir, gt, settings)
    assert sid is not None
    return r, gt, sid


def test_chain_g1s0_verdict(settings: Settings) -> None:
    r, gt, sid = setup(settings)
    tracer = Tracer(settings)
    v = tracer.trace(r.run_id, sid, make_symptom_check(gt, settings))
    assert v.status == "confirmed"
    assert (v.entry_agent, v.entry_turn) == ("A", "A#1")
    assert v.paths == [["A", "B", "C", "D", "E"]]
    assert v.ranking[0]["candidate"] == v.entry_event_id
    assert v.ranking[0]["pattern"] == 1.0
    assert v.replays_used >= 1
    with EventStore.for_run(r.run_dir, readonly=True) as s:
        assert s.verdicts() == [v]
        entry = s.get(str(v.entry_event_id))
    assert entry.output_ref == f"sha256:{gt.poisoned_page_sha256}"


def test_tracer_visits_each_event_at_most_once(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mastrace.provenance import event_graph

    graphs: list[event_graph.EventGraph] = []
    orig = event_graph.EventGraph.from_run.__func__  # type: ignore[attr-defined]

    def spy(cls: type, run_dir: Path) -> event_graph.EventGraph:
        g: event_graph.EventGraph = orig(cls, run_dir)
        graphs.append(g)
        return g

    monkeypatch.setattr(event_graph.EventGraph, "from_run", classmethod(spy))
    r, gt, sid = setup(settings)
    graphs.clear()
    Tracer(settings).trace(r.run_id, sid, make_symptom_check(gt, settings))
    assert graphs and max(graphs[0].visits.values()) == 1


def test_g2_verdict(settings: Settings) -> None:
    r, gt, sid = setup(settings, attack="g2s1")
    v = Tracer(settings).trace(r.run_id, sid, make_symptom_check(gt, settings))
    assert (v.status, v.entry_agent, v.entry_turn) == ("confirmed", "A", "A#1")


def test_fanin_blames_a_not_b(settings: Settings) -> None:
    r, gt, sid = setup(settings, config="s1_fanin")
    v = Tracer(settings).trace(r.run_id, sid, make_symptom_check(gt, settings))
    assert (v.entry_agent, v.entry_turn) == ("A", "A#1")
    assert v.paths == [["A", "C", "D", "E"]]


def test_fanout_follows_branch(settings: Settings) -> None:
    r, gt, sid = setup(settings, config="s1_fanout")
    v = Tracer(settings).trace(r.run_id, sid, make_symptom_check(gt, settings))
    assert v.paths == [["A", "C", "E"]]


def test_unconfirmed_when_symptom_never_goes_away(settings: Settings) -> None:
    r, _gt, sid = setup(settings)
    v = Tracer(settings).trace(r.run_id, sid, lambda run_id: True)
    assert v.status == "unconfirmed" and v.entry_agent is None
    assert len(v.ranking) >= 1


def test_ngram_jaccard() -> None:
    assert jaccard(ngrams("hello world", 5), ngrams("Hello   World", 5)) == 1.0
    assert jaccard(ngrams("abcdefgh", 5), ngrams("zzzzzzzz", 5)) == 0.0
    assert jaccard(set(), set()) == 0.0


def test_tracing_twice_gives_distinct_verdicts(settings: Settings) -> None:
    r, gt, sid = setup(settings)
    t = Tracer(settings)
    a = t.trace(r.run_id, sid, make_symptom_check(gt, settings))
    b = t.trace(r.run_id, sid, make_symptom_check(gt, settings))
    assert a.verdict_id.endswith(":1") and b.verdict_id.endswith(":2")
    assert (a.entry_turn, a.paths) == (b.entry_turn, b.paths)


def test_whiteboard_attack_and_trace(settings: Settings) -> None:
    """answers.md D3: the provisional whiteboard layout runs an attack and traces it.

    With every agent gullible the payload reaches E first over the shorter route A→C→E,
    so that is the causal path; with C resistant it is the intended route A→B→D→E.
    """
    r, gt, sid = setup(settings, config="s3_whiteboard")
    v = Tracer(settings).trace(r.run_id, sid, make_symptom_check(gt, settings))
    assert (v.status, v.entry_agent, v.entry_turn) == ("confirmed", "A", "A#1")
    assert v.paths == [["A", "C", "E"]]
    s2 = Settings(data_dir=settings.data_dir.parent / "resistant_c")
    r2, gt2, sid2 = setup(s2, config="s3_whiteboard", policy_overrides={"C": "resistant"})
    v2 = Tracer(s2).trace(r2.run_id, sid2, make_symptom_check(gt2, s2))
    assert (v2.status, v2.entry_turn) == ("confirmed", "A#1")
    marks = {tuple(x["path"]): x["status"] for x in v2.replays if x["kind"] == "path"}
    assert marks == {("A", "B", "D", "E"): "causal", ("A", "C", "E"): "non_causal"}


def test_downstream_secret_read_is_not_the_entry(settings: Settings) -> None:
    """Neutralizing E's read of credentials.txt also removes the leak, but it is derived."""
    r, gt, sid = setup(settings)
    v = Tracer(settings).trace(r.run_id, sid, make_symptom_check(gt, settings))
    singles = {x["candidate"]: x["confirmed"] for x in v.replays if x["kind"] == "candidate"}
    with EventStore.for_run(r.run_dir, readonly=True) as s:
        reads = [e for e in singles if s.get(e).meta.get("tool") == "read_file"]
    assert reads and all(singles[e] for e in reads)  # the read does remove the symptom
    assert v.confirmed_entry_events == [v.entry_event_id]
    assert v.entry_event_id not in reads
