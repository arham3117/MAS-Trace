"""P5.4: static architecture boundaries (I2, I8).

The checks work on any source tree, so they are also run on synthetic trees containing a
deliberate violation to show they catch it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[2] / "mastrace"
GT_MODULES = ("mastrace.groundtruth", "mastrace.evaluation", "mastrace.control.injector")
MODEL_CALLERS = {"runtime/agent_runner.py", "analysis/investigator.py"}
_GW_CALL = re.compile(r"\b\w*model_g(?:ate)?w(?:ay)?\w*\s*\.\s*call\s*\(")


def module_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def imports_of(root: Path, path: Path) -> set[str]:
    """Absolute module names imported by a file (relative imports resolved)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    me = module_name(root, path)
    pkg = me if path.name == "__init__.py" else me.rsplit(".", 1)[0]
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = pkg.split(".")[: len(pkg.split(".")) - node.level + 1]
                base = ".".join([*anchor, base]) if base else ".".join(anchor)
            out.add(base)
            out.update(f"{base}.{a.name}" for a in node.names)
    return out


def import_graph(root: Path) -> dict[str, set[str]]:
    mods = {module_name(root, p): p for p in sorted(root.rglob("*.py"))}
    return {m: {i for i in imports_of(root, p) if i in mods} for m, p in mods.items()}


def reachable(graph: dict[str, set[str]], start: str) -> set[str]:
    seen, stack = {start}, [start]
    while stack:
        for nxt in graph.get(stack.pop(), set()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def gt_violations(root: Path) -> list[str]:
    """Analysis modules that reach ground truth (directly or transitively) or name its DB."""
    graph = import_graph(root)
    bad = []
    for path in sorted((root / "analysis").rglob("*.py")):
        mod = module_name(root, path)
        hits = sorted(m for m in reachable(graph, mod) if m.startswith(GT_MODULES))
        if hits:
            bad.append(f"{mod} reaches {hits}")
        if "ground_truth" in path.read_text(encoding="utf-8"):
            bad.append(f"{mod} mentions ground_truth")
    return bad


def model_call_violations(root: Path) -> list[str]:
    """Modules other than the agent runner and investigator that call the model gateway."""
    bad = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel in MODEL_CALLERS or rel == "mediation/model_gateway.py":
            continue
        if _GW_CALL.search(path.read_text(encoding="utf-8")):
            bad.append(rel)
    return bad


# -- the real package ---------------------------------------------------------------


def test_analysis_cannot_import_groundtruth() -> None:
    assert gt_violations(PKG_ROOT) == []


def test_no_llm_in_core() -> None:
    assert model_call_violations(PKG_ROOT) == []


def test_agent_runner_is_a_caller() -> None:
    """Guard against the regex silently matching nothing."""
    src = (PKG_ROOT / "runtime" / "agent_runner.py").read_text()
    assert _GW_CALL.search(src)


# -- the checks catch violations --------------------------------------------------------


def make_tree(tmp: Path, files: dict[str, str]) -> Path:
    root = tmp / "mastrace"
    for rel, src in {
        "__init__.py": "",
        "analysis/__init__.py": "",
        "groundtruth/__init__.py": "",
        "groundtruth/store.py": "X = 1\n",
        "util/__init__.py": "",
        **files,
    }.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
    return root


def test_detects_direct_import(tmp_path: Path) -> None:
    root = make_tree(
        tmp_path, {"analysis/scratch.py": "from mastrace.groundtruth.store import X\n"}
    )
    [v] = gt_violations(root)
    assert v == "mastrace.analysis.scratch reaches ['mastrace.groundtruth.store']"


def test_detects_transitive_and_relative_import(tmp_path: Path) -> None:
    root = make_tree(
        tmp_path,
        {
            "util/helper.py": "from ..groundtruth import store\n",
            "analysis/scratch.py": "import mastrace.util.helper\n",
        },
    )
    assert len(gt_violations(root)) == 1


def test_detects_db_path_literal(tmp_path: Path) -> None:
    root = make_tree(tmp_path, {"analysis/scratch.py": 'P = "data/ground_truth.sqlite"\n'})
    assert gt_violations(root) == ["mastrace.analysis.scratch mentions ground_truth"]


def test_detects_model_gateway_call(tmp_path: Path) -> None:
    root = make_tree(
        tmp_path,
        {
            "mediation/router.py": "def f(model_gateway):\n    return model_gateway.call(1)\n",
            "runtime/agent_runner.py": "def g(self):\n    self.model_gateway.call(1)\n",
        },
    )
    assert model_call_violations(root) == ["mediation/router.py"]
