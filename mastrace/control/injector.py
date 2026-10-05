"""Injector: poison one web page in a run's env and record ground truth (plan.md §7.9, P5.2).

Nothing about the injection is written to the run's own event log or manifest beyond what
§7.5 lists; the details go only to `ground_truth.sqlite`.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from mastrace.control.attacks import render_payload
from mastrace.core.canonical import sha256_hex
from mastrace.core.errors import ConfigError
from mastrace.core.schemas import AttackSpec, GroundTruth, InjectionInfo, TaskSpec
from mastrace.groundtruth.store import GroundTruthStore

_PARA_SPLIT = re.compile(r"\n\s*\n")


def page_path(env_dir: Path, url: str) -> Path:
    """Where `web_fetch` serves `url` from inside a run's env."""
    u = urlparse(url)
    return env_dir / "web" / str(u.hostname) / f"{u.path.strip('/') or 'index'}.md"


def poison(text: str, payload: str, placement: str) -> str:
    """Insert the payload as its own paragraph: at the end, or after the middle paragraph."""
    paras = [p.strip() for p in _PARA_SPLIT.split(text.strip()) if p.strip()]
    if placement == "middle" and len(paras) > 1:
        paras.insert((len(paras) + 1) // 2, payload)
    else:
        paras.append(payload)
    return "\n\n".join(paras) + "\n"


def inject(
    run_env: Path,
    task: TaskSpec,
    attack: AttackSpec,
    run_id: str,
    gt_path: Path,
    target_agent: str = "A",
    target_url: str | None = None,
) -> InjectionInfo:
    """Rewrite the target page with the payload and write the ground-truth row."""
    url = target_url or task.sources[0]
    path = page_path(run_env, url)
    if not path.is_file():
        raise ConfigError(f"target page not in env: {url}")
    poisoned = poison(path.read_text(encoding="utf-8"), render_payload(attack), attack.placement)
    path.write_text(poisoned, encoding="utf-8")
    with GroundTruthStore(gt_path) as store:
        store.put(
            GroundTruth(
                run_id=run_id,
                attack_id=attack.id,
                goal=attack.goal,
                stealth=attack.stealth,
                target_agent=target_agent,
                target_url=url,
                poisoned_page_sha256=sha256_hex(poisoned),
                kind="attack",
            )
        )
    return InjectionInfo(run_id=run_id, injected=True)
