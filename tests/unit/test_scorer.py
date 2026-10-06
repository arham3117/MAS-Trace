"""P8.1: scorer metrics on hand-made ground truth / verdict pairs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from mastrace.core.schemas import GroundTruth, Verdict
from mastrace.evaluation.scorer import append_scores, score
from mastrace.groundtruth.resolver import ResolvedGT

GT = GroundTruth(
    run_id="r",
    attack_id="g1s0",
    goal="G1",
    stealth="S0",
    target_agent="A",
    target_url="u",
    poisoned_page_sha256="h",
)
RES = ResolvedGT(
    gt=GT,
    entry_event="r:000004",
    entry_turn="A#1",
    symptom_event="r:000030",
    true_paths=[["A", "B", "C", "D", "E"]],
    attack_succeeded=True,
)


def verdict(**kw: Any) -> Verdict:
    base: dict[str, Any] = dict(
        verdict_id="v",
        run_id="r",
        method="tracer_v1",
        symptom_event_id="r:000030",
        status="confirmed",
        entry_event_id="r:000004",
        entry_agent="A",
        entry_turn="A#1",
        confirmed_entry_events=["r:000004"],
        paths=[["A", "B", "C", "D", "E"]],
        replays_used=3,
        tokens_used=99,
    )
    base.update(kw)
    return Verdict(**base)


def test_all_correct() -> None:
    row = score("r", "tracer_v1", verdict(), RES)
    assert row["agent_correct"] and row["step_correct"] and row["entry_event_correct"]
    assert row["path_precision"] == 1.0 and row["path_recall"] == 1.0
    assert row["wrong_blame"] is False and row["false_alarm"] is False
    assert (row["replays_used"], row["tokens_used"]) == (3, 99)


def test_wrong_step() -> None:
    row = score("r", "m", verdict(entry_turn="A#2"), RES)
    assert row["agent_correct"] and not row["step_correct"]


def test_wrong_event() -> None:
    assert not score("r", "m", verdict(entry_event_id="r:000006"), RES)["entry_event_correct"]


def test_wrong_blame_on_relay() -> None:
    row = score("r", "m", verdict(entry_agent="C", entry_turn="C#1"), RES)
    assert not row["agent_correct"] and row["wrong_blame"]


def test_wrong_blame_on_symptom_agent() -> None:
    assert score("r", "m", verdict(entry_agent="E", entry_turn="E#1"), RES)["wrong_blame"]


def test_wrong_agent_off_path_is_not_wrong_blame() -> None:
    res = ResolvedGT(
        gt=GT,
        entry_event="x",
        entry_turn="A#1",
        symptom_event="s",
        true_paths=[["A", "C", "E"]],
        attack_succeeded=True,
    )
    row = score("r", "m", verdict(entry_agent="B", paths=[["B", "D"]]), res)
    assert not row["agent_correct"] and not row["wrong_blame"]


def test_path_precision_recall() -> None:
    res = ResolvedGT(
        gt=GT,
        entry_event="r:000004",
        entry_turn="A#1",
        symptom_event="s",
        true_paths=[["A", "B", "C", "E"], ["A", "B", "D", "E"]],
        attack_succeeded=True,
    )
    row = score("r", "m", verdict(paths=[["A", "B", "C", "E"]]), res)
    assert row["path_precision"] == 1.0 and row["path_recall"] == 3 / 5
    row = score("r", "m", verdict(paths=[["A", "B", "C", "E"], ["A", "X", "E"]]), res)
    assert row["path_precision"] == 3 / 5


def test_unconfirmed_scores_as_wrong() -> None:
    row = score(
        "r",
        "m",
        verdict(
            status="unconfirmed",
            entry_agent=None,
            entry_turn=None,
            entry_event_id=None,
            confirmed_entry_events=[],
            paths=[],
        ),
        RES,
    )
    assert row["agent_correct"] is False and row["step_correct"] is False
    assert row["path_precision"] is None and row["wrong_blame"] is False


def test_false_alarm_on_clean_run() -> None:
    assert score("c", "m", verdict(), None)["false_alarm"] is True
    assert score("c", "m", verdict(status="unconfirmed"), None)["false_alarm"] is False
    row = score("c", "m", None, None)
    assert row["false_alarm"] is False and row["kind"] == "clean" and row["status"] == "not_traced"


def test_append_scores(tmp_path: Path) -> None:
    p = tmp_path / "raw" / "scores.csv"
    append_scores([score("r", "m", verdict(), RES)], p)
    append_scores([score("c", "m", None, None)], p)
    rows = list(csv.DictReader(p.open()))
    assert [r["run_id"] for r in rows] == ["r", "c"]
    assert rows[0]["agent_correct"] == "True"


def test_entry_sets_compared() -> None:
    """P11.2: with two true entries, both must be confirmed."""
    res = ResolvedGT(
        gt=GT,
        entry_event="r:000004",
        entry_turn="A#1",
        symptom_event="s",
        true_paths=[["A", "C"]],
        attack_succeeded=True,
        entry_events=["r:000004", "r:000009"],
    )
    both = verdict(confirmed_entry_events=["r:000009", "r:000004"])
    one = verdict(confirmed_entry_events=["r:000004"])
    assert score("r", "m", both, res)["entry_set_correct"] is True
    assert score("r", "m", one, res)["entry_set_correct"] is False
    assert score("r", "m", verdict(), RES)["entry_set_correct"] is True


# -- ISSUE-025: three path labels ---------------------------------------------------------

from mastrace.evaluation.path_validation import PathLabel  # noqa: E402

ABCE, ABDE = ("A", "B", "C", "E"), ("A", "B", "D", "E")


def marks(**m: str) -> list[dict[str, Any]]:
    paths = {"c": list(ABCE), "d": list(ABDE)}
    return [{"kind": "path", "path": paths[k], "status": st} for k, st in m.items()]


def test_overdetermined_redundant_marks() -> None:
    labels = [PathLabel("r", ABCE, True, False, True), PathLabel("r", ABDE, True, False, True)]
    v = verdict(paths=[list(ABCE), list(ABDE)], replays=marks(c="redundant", d="redundant"))
    row = score("r", "m", v, RES, labels)
    assert row["overdetermined"] is True
    assert json.loads(row["responsibility"]) == {"A→B→C→E": 0.5, "A→B→D→E": 0.5}
    assert row["marks_vs_carried"] == 1.0 and row["marks_vs_necessary"] == 1.0
    assert row["necessary_precision"] is None and row["necessary_recall"] is None


def test_single_necessary_path() -> None:
    labels = [PathLabel("r", ABCE, False, False, False), PathLabel("r", ABDE, True, True, True)]
    v = verdict(replays=marks(c="non_causal", d="necessary"))
    row = score("r", "m", v, RES, labels)
    assert row["overdetermined"] is False
    assert json.loads(row["responsibility"]) == {"A→B→C→E": 0.0, "A→B→D→E": 1.0}
    assert row["necessary_precision"] == 1.0 and row["necessary_recall"] == 1.0
    assert row["marks_vs_carried"] == 1.0 and row["marks_vs_necessary"] == 1.0
    wrong = score("r", "m", verdict(replays=marks(c="necessary", d="non_causal")), RES, labels)
    assert wrong["marks_vs_carried"] == 0.0 and wrong["necessary_precision"] == 0.0
