"""Gate runner and reports (plan.md §9.4, P8.3)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from mastrace.core.logging import code_version
from mastrace.settings import REPO_ROOT

GATES_DIR = REPO_ROOT / "reports" / "gates"
CURRENT = GATES_DIR / "_current.jsonl"
TEST_DIR = REPO_ROOT / "tests" / "gates"


@dataclass(frozen=True)
class GateOutcome:
    """Result of one gate run."""

    stage: int
    overall: str
    report: Path
    exit_code: int


def gate_files(stage: int) -> list[str]:
    """Common suite plus every stage suite up to `stage`."""
    return [str(TEST_DIR / "test_gate_common.py")] + [
        str(TEST_DIR / f"test_gate_stage{s}.py") for s in range(1, stage + 1)
    ]


def run_gate(stage: int, include_model: bool = True, extra: list[str] | None = None) -> GateOutcome:
    """Run the gate suites with pytest, then write `reports/gates/stage<N>_<date>.md`."""
    GATES_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT.unlink(missing_ok=True)
    marker = "gate" if include_model else "gate and not model"
    cmd = [sys.executable, "-m", "pytest", "-q", "-m", marker, *gate_files(stage), *(extra or [])]
    env = {**os.environ, "MASTRACE_GATE_STAGE": str(stage)}
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, check=False)
    results = read_results()
    report = write_report(stage, results, pytest_exit=proc.returncode)
    return GateOutcome(stage, overall_of(results, proc.returncode), report, proc.returncode)


def read_results(path: Path = CURRENT) -> list[dict[str, object]]:
    """Check results written by the gate suites."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def overall_of(results: list[dict[str, object]], pytest_exit: int) -> str:
    """PASS only if every check passed and pytest itself succeeded."""
    kinds = {str(r["result"]) for r in results}
    if "FAIL" in kinds or (pytest_exit not in (0, 5) and "INCONCLUSIVE" not in kinds):
        return "FAIL"
    if "INCONCLUSIVE" in kinds:
        return "INCONCLUSIVE"
    return "PASS" if results else "FAIL"


def write_report(
    stage: int, results: list[dict[str, object]], pytest_exit: int, day: date | None = None
) -> Path:
    """Render the §9.4 template."""
    day = day or date.today()
    lines = [
        f"# Gate report: Stage {stage} ({day.isoformat()}, code {code_version()})",
        "",
        "| Check | Result | Runs | Notes / run ids |",
        "|---|---|---|---|",
    ]
    for r in results:
        runs = r.get("runs") or []
        assert isinstance(runs, list)
        sample = ", ".join(str(x) for x in runs[:3]) + (" …" if len(runs) > 3 else "")
        notes = str(r.get("notes") or "")
        lines.append(
            f"| {r['check']} | {r['result']} {r['passed']}/{r['total']} | {len(runs)} | "
            f"{notes + ' · ' if notes else ''}{sample} |"
        )
    lines += [
        "",
        f"**Overall:** {overall_of(results, pytest_exit)}",
        f"**pytest exit code:** {pytest_exit}",
        "**Issues opened:** see issue.md",
        "",
    ]
    path = GATES_DIR / f"stage{stage}_{day.isoformat()}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def stage_status() -> dict[int, tuple[str, str]]:
    """Latest report per stage: {stage: (overall, report file name)}."""
    out: dict[int, tuple[str, str]] = {}
    for p in sorted(GATES_DIR.glob("stage*_*.md")):
        stage = int(p.name[5 : p.name.index("_")])
        overall = next(
            (
                ln.split("**Overall:**", 1)[1].strip()
                for ln in p.read_text().splitlines()
                if ln.startswith("**Overall:**")
            ),
            "UNKNOWN",
        )
        out[stage] = (overall, p.name)
    return out
