"""Task templates: `env/templates/<task_id>/task.yaml` (plan.md §7.8)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mastrace.core.errors import ConfigError
from mastrace.core.schemas import TaskSpec
from mastrace.settings import REPO_ROOT

TEMPLATES_DIR = REPO_ROOT / "env" / "templates"


def load_task(task_id: str, templates_dir: Path = TEMPLATES_DIR) -> TaskSpec:
    """Load and validate a task's `task.yaml`."""
    path = templates_dir / task_id / "task.yaml"
    if not path.is_file():
        raise ConfigError(f"task not found: {path}")
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping")
    raw.setdefault("id", task_id)
    return TaskSpec.model_validate(raw)


def all_task_ids(templates_dir: Path = TEMPLATES_DIR) -> list[str]:
    """Every task directory that has a task.yaml, sorted."""
    return sorted(p.parent.name for p in templates_dir.glob("*/task.yaml"))
