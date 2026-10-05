"""Load and validate graph configs (plan.md §7.1, P3.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mastrace.core.canonical import canonical_json, sha256_hex
from mastrace.core.errors import ConfigError
from mastrace.core.schemas import GraphConfig
from mastrace.mediation.tools import tool_names
from mastrace.settings import REPO_ROOT

GRAPHS_DIR = REPO_ROOT / "configs" / "graphs"
ROLES_DIR = REPO_ROOT / "prompts" / "roles"


def resolve_config_path(name_or_path: str | Path) -> Path:
    """Accept `s1_chain`, `s1_chain.yaml` or a path to a YAML file."""
    p = Path(name_or_path)
    if p.suffix in (".yaml", ".yml") and p.exists():
        return p
    candidate = GRAPHS_DIR / f"{p.stem}.yaml"
    if candidate.exists():
        return candidate
    raise ConfigError(f"graph config not found: {name_or_path}")


def load_graph(name_or_path: str | Path, roles_dir: Path = ROLES_DIR) -> GraphConfig:
    """Load a graph config and check rules 1-7 (rule 8 is checked at run start)."""
    path = resolve_config_path(name_or_path)
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping")
    cfg = GraphConfig.model_validate(raw)
    cfg.check_resources(roles_dir, tool_names())
    return cfg


def config_hash(cfg: GraphConfig) -> str:
    """SHA-256 of the config's canonical JSON."""
    return sha256_hex(canonical_json(cfg.model_dump(mode="json")))


def all_graph_names() -> list[str]:
    """Names of every config in `configs/graphs/`, sorted."""
    return sorted(p.stem for p in GRAPHS_DIR.glob("*.yaml"))
