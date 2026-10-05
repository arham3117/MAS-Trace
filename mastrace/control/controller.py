"""Controller: entry point for runs, gates and experiments (plan.md P3.5, P8.3)."""

from __future__ import annotations

from mastrace.mediation.model_gateway import Mode
from mastrace.runtime.run import RunResult, run_once


def run_with_attack(
    config: str,
    task_id: str,
    attack_id: str | None,
    model_key: str,
    seed: int,
    mode: Mode = "record",
    overwrite: bool = False,
) -> RunResult:
    """Run one configuration; attack runs are wired to the injector in P5.2."""
    if attack_id is not None:
        raise NotImplementedError("attack runs need the injector (plan.md P5.2)")
    return run_once(config, task_id, None, model_key, seed, mode=mode, overwrite=overwrite)
