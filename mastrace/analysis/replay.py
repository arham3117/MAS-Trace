"""Replay engine: re-run a recorded run through the caches, optionally with overrides
(plan.md §7.7, P7.1).

Replays reuse the original manifest (config, task, model, seed, scripted options) and a copy
of the original `env/`, and run the gateways in `replay` mode. Every step before the first
override hits the cache; later steps see different inputs and run live.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import cast

from mastrace.core.schemas import GraphConfig, Override
from mastrace.mediation.providers.scripted import Policy
from mastrace.runtime.run import read_manifest, run_once
from mastrace.settings import Settings, get_settings


def _next_index(settings: Settings, run_id: str) -> int:
    pattern = re.compile(re.escape(run_id) + r"__r(\d+)")
    used = [
        int(m.group(1))
        for p in settings.runs_dir.glob(f"{run_id}__r*")
        if (m := pattern.fullmatch(p.name))
    ]
    return max(used, default=0) + 1


def replay(
    run_id: str,
    overrides: Sequence[Override] = (),
    n: int = 1,
    settings: Settings | None = None,
) -> list[str]:
    """Replay `run_id` `n` times with `overrides`; return the replay run IDs
    (`<run_id>__r<k>`, numbered after any existing replays).

    Each replay salts its own live cache entries with its run ID (ISSUE-008), so the `n`
    replays are independent samples after the override point.
    """
    settings = settings or get_settings()
    run_dir = settings.runs_dir / run_id
    m = read_manifest(run_dir)
    cfg = GraphConfig.model_validate(m.config)
    out = []
    for _ in range(n):
        rid = f"{run_id}__r{_next_index(settings, run_id)}"
        run_once(
            cfg,
            m.task_id,
            m.attack_id,
            m.model_key,
            m.seed,
            mode="replay",
            overrides=overrides,
            settings=settings,
            run_id=rid,
            env_source=run_dir / "env",
            policy_overrides=cast(dict[str, Policy], m.policy_overrides),
            feedback_rounds=m.feedback_rounds,
            replay_of=run_id,
            replay_salt=rid,
        )
        out.append(rid)
    return out
