"""Attack library: load, gate and render attack specs (plan.md §7.9, P5.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mastrace.core.errors import ConfigError
from mastrace.core.schemas import AttackSpec
from mastrace.settings import REPO_ROOT

ATTACKS_DIR = REPO_ROOT / "attacks"
# Phase the build has reached for attack gating; raise to 13 when P13.2 enables S2/S3.
CURRENT_PHASE = 5


class AttackDisabled(ConfigError):
    """The attack is drafted but not enabled in the current phase."""


def load_attack(
    attack_id: str, allow_disabled: bool = False, attacks_dir: Path = ATTACKS_DIR
) -> AttackSpec:
    """Load `attacks/<id>.yaml`; refuse specs enabled only in a later phase."""
    path = attacks_dir / f"{attack_id}.yaml"
    if not path.is_file():
        raise ConfigError(f"attack not found: {path}")
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    spec = AttackSpec.model_validate(raw)
    if spec.id != attack_id:
        raise ConfigError(f"{path}: id {spec.id!r} does not match file name")
    if spec.enabled_from_phase > CURRENT_PHASE and not allow_disabled:
        raise AttackDisabled(
            f"attack {attack_id} is enabled from phase {spec.enabled_from_phase} "
            f"(current {CURRENT_PHASE}); pass --allow-disabled to use it"
        )
    return spec


def render_payload(spec: AttackSpec) -> str:
    """The attacker's paragraph with its parameters filled in (one paragraph, no newlines)."""
    text = spec.template.strip()
    for k, v in sorted(spec.params.items()):
        if v is not None:
            text = text.replace("{" + k + "}", v)
    return " ".join(text.split())


def marker_of(spec: AttackSpec) -> str | None:
    """The G2 marker text (without the `MARKER:` prefix)."""
    return spec.params.get("marker")


def all_attack_ids(attacks_dir: Path = ATTACKS_DIR) -> list[str]:
    """Every attack spec ID, sorted."""
    return sorted(p.stem for p in attacks_dir.glob("*.yaml"))
