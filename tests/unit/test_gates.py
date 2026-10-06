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
