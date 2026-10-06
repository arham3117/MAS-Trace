"""P8.3: gate report rendering and overall result."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from mastrace.control import gates


def res(check: str, result: str) -> dict[str, object]:
    return {"check": check, "result": result, "passed": 5, "total": 5, "notes": "", "runs": ["r1"]}


def test_overall() -> None:
    assert gates.overall_of([res("a", "PASS")], 0) == "PASS"
    assert gates.overall_of([res("a", "PASS"), res("b", "FAIL")], 1) == "FAIL"
    assert gates.overall_of([res("a", "PASS"), res("b", "INCONCLUSIVE")], 1) == "INCONCLUSIVE"
    assert gates.overall_of([], 0) == "FAIL"
    assert gates.overall_of([res("a", "PASS")], 2) == "FAIL"  # pytest error without a result


def test_report_and_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gates, "GATES_DIR", tmp_path)
    p = gates.write_report(1, [res("G-C1[s1_chain]", "PASS")], 0, day=date(2026, 10, 5))
    text = p.read_text()
    assert p.name == "stage1_2026-10-05.md"
    assert "| G-C1[s1_chain] | PASS 5/5 | 1 | r1 |" in text and "**Overall:** PASS" in text
    assert gates.stage_status() == {1: ("PASS", "stage1_2026-10-05.md")}


def test_gate_files() -> None:
    names = [Path(f).name for f in gates.gate_files(2)]
    assert names == ["test_gate_common.py", "test_gate_stage1.py", "test_gate_stage2.py"]


def test_gate_refuses_dirty_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    """ISSUE-029: gate evidence must come from committed code."""
    monkeypatch.setattr(gates, "code_version", lambda: "abc1234-dirty")
    with pytest.raises(gates.DirtyTree, match="dirty"):
        gates.run_gate(1)


def test_run_versions_section(tmp_path: Path) -> None:
    import json

    p = tmp_path / "c.jsonl"
    p.write_text(
        "\n".join(
            json.dumps({"type": "run_version", "run": f"r{i}", "code_version": v})
            for i, v in enumerate(["aaa", "aaa", "bbb-dirty"])
        )
    )
    text = "\n".join(gates.run_versions_section(p))
    assert "`aaa`: 2" in text and "Dirty-stamped runs: **1**" in text


def test_report_includes_propagation_and_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1d / ISSUE-029: the written report really contains both sections."""
    import json

    monkeypatch.setattr(gates, "GATES_DIR", tmp_path)
    cur = tmp_path / "_current.jsonl"
    hops = {h: {"anchor": h == "A", "overlap": False, "jaccard": 0.1} for h in gates.HOPS}
    cur.write_text(
        "\n".join(
            json.dumps(x)
            for x in [
                {
                    "type": "propagation",
                    "config": "s1_chain",
                    "goal": "G1",
                    "hops": hops,
                    "entry_handling": "omitted",
                },
                {"type": "run_version", "run": "r", "code_version": "abc1234"},
            ]
        )
    )
    p = gates.write_report(
        1,
        [res("G1-1[dev_open]", "INCONCLUSIVE")],
        1,
        day=date(2026, 10, 5),
        current=cur,
        code="7a691d6",
    )
    text = p.read_text()
    assert "code 7a691d6" in text
    assert "## Propagation by hop" in text and "| s1_chain | G1 | 1 | 1 | 0 | 0 |" in text
    assert "## Code versions of real-model runs" in text and "Dirty-stamped runs: **0**" in text
