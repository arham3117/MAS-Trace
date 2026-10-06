"""answers.md D6: anchor labels vs replay necessity and sufficiency."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mastrace.control.controller import run_with_attack
from mastrace.evaluation.path_validation import label_run
from mastrace.settings import Settings


def labels(
    tmp_path: Path, **kw: Any
) -> dict[tuple[str, ...], tuple[bool, bool | None, bool | None]]:
    st = Settings(data_dir=tmp_path / "data")
    r = run_with_attack(
        "s3_mixed_two_paths", "t01", "g1s0", "scripted_gullible", 1, settings=st, **kw
    )
    return {x.path: (x.anchor_true, x.replay_true, x.sufficient) for x in label_run(r.run_id, st)}


def test_single_carrier_all_labels_agree(tmp_path: Path) -> None:
    got = labels(tmp_path, policy_overrides={"C": "resistant"})
    assert got == {
        ("A", "B", "C", "E"): (False, False, False),
        ("A", "B", "D", "E"): (True, True, True),
    }


def test_redundant_paths_carried_and_sufficient_but_not_necessary(tmp_path: Path) -> None:
    got = labels(tmp_path)
    assert got == {
        ("A", "B", "C", "E"): (True, False, True),
        ("A", "B", "D", "E"): (True, False, True),
    }
