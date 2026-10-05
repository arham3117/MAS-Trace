"""Copy a task template into a run's `env/` and fill in the canary (plan.md §7.8, P4.1)."""

from __future__ import annotations

import shutil
from pathlib import Path

from mastrace.core.canonical import canonical_json, sha256_hex

CANARY_TOKEN = "{{CANARY}}"


def canary_for(seed: int) -> str:
    """`CANARY-` plus the first 8 hex characters of sha256(seed)."""
    return "CANARY-" + sha256_hex(str(seed))[:8]


def env_snapshot_hash(env_dir: Path) -> str:
    """Hash of every file under `env_dir` (relative path -> content hash), order-independent."""
    files = {
        p.relative_to(env_dir).as_posix(): sha256_hex(p.read_bytes())
        for p in sorted(env_dir.rglob("*"))
        if p.is_file() and p.name != "outbox.jsonl"
    }
    return sha256_hex(canonical_json(files))


def materialize(template_dir: Path, env_dir: Path, seed: int) -> str:
    """Copy `web/` and `files/` of the template, substitute the canary, return the snapshot hash."""
    env_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("web", "files"):
        src = template_dir / sub
        if src.is_dir():
            shutil.copytree(src, env_dir / sub, dirs_exist_ok=True)
    canary = canary_for(seed)
    for p in sorted(env_dir.rglob("*")):
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            if CANARY_TOKEN in text:
                p.write_text(text.replace(CANARY_TOKEN, canary), encoding="utf-8")
    return env_snapshot_hash(env_dir)
