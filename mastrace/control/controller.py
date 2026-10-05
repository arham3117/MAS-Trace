"""Controller: entry point for runs, gates and experiments (plan.md P3.5, P5.2, P8.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mastrace.control.attacks import load_attack
from mastrace.control.injector import inject
from mastrace.core.schemas import GraphConfig, TaskSpec
from mastrace.mediation.model_gateway import Mode
from mastrace.runtime.run import RunResult, run_once
from mastrace.settings import Settings, get_settings


def run_with_attack(
    config: str | Path | GraphConfig,
    task_id: str,
    attack_id: str | None,
    model_key: str,
    seed: int,
    mode: Mode = "record",
    overwrite: bool = False,
    settings: Settings | None = None,
    allow_disabled: bool = False,
    target_agent: str = "A",
    **kwargs: Any,
) -> RunResult:
    """Run one configuration; for attack runs, poison the target page first."""
    settings = settings or get_settings()
    hook = None
    if attack_id is not None:
        spec = load_attack(attack_id, allow_disabled=allow_disabled)

        def hook(env_dir: Path, task: TaskSpec, run_id: str) -> None:
            inject(env_dir, task, spec, run_id, settings.ground_truth_path, target_agent)

    return run_once(
        config,
        task_id,
        attack_id,
        model_key,
        seed,
        mode=mode,
        overwrite=overwrite,
        settings=settings,
        inject=hook,
        **kwargs,
    )
