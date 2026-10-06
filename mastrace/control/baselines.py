"""Clean baselines: utility of clean runs per task and model (plan.md P4.5)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from mastrace.environment.checkers import utility
from mastrace.environment.tasks import all_task_ids, load_task
from mastrace.runtime.run import run_once
from mastrace.settings import Settings, get_settings

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports" / "baselines"


def clean_baseline(
    config: str,
    model_keys: Sequence[str],
    tasks: Sequence[str] | None = None,
    seed: int = 1,
    settings: Settings | None = None,
) -> dict[str, dict[str, tuple[str, float]]]:
    """Run every task clean for each model; return {model: {task: (status, utility)}}."""
    settings = settings or get_settings()
    tasks = list(tasks or all_task_ids(settings.templates_dir))
    out: dict[str, dict[str, tuple[str, float]]] = {}
    for model in model_keys:
        out[model] = {}
        for task_id in tasks:
            r = run_once(config, task_id, None, model, seed, settings=settings, overwrite=True)
            task = load_task(task_id, settings.templates_dir)
            out[model][task_id] = (
                r.status,
                utility(r.run_dir, task.expected_facts, task.match_any),
            )
    return out


def baseline_markdown(
    config: str, results: dict[str, dict[str, tuple[str, float]]], note: str = ""
) -> str:
    """Render the utility table."""
    models = list(results)
    tasks = sorted({t for m in models for t in results[m]})
    lines = [f"# Clean baseline: {config}", ""]
    if note:
        lines += [note, ""]
    lines += ["| Task | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for t in tasks:
        cells = [f"{results[m][t][1]:.2f} ({results[m][t][0]})" for m in models]
        lines.append(f"| {t} | " + " | ".join(cells) + " |")
    means = [sum(u for _, u in results[m].values()) / len(results[m]) for m in models]
    lines.append("| **mean** | " + " | ".join(f"**{x:.0%}**" for x in means) + " |")
    return "\n".join(lines) + "\n"


def write_baseline(
    config: str, results: dict[str, dict[str, tuple[str, float]]], note: str = ""
) -> Path:
    """Write `reports/baselines/clean_<config>.md`."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"clean_{config}.md"
    path.write_text(baseline_markdown(config, results, note), encoding="utf-8")
    return path
