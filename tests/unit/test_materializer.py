"""P4.1: environment materializer."""

from __future__ import annotations

import re
from pathlib import Path

from mastrace.core.canonical import sha256_hex
from mastrace.environment.materializer import canary_for, env_snapshot_hash, materialize

TEMPLATE = Path(__file__).resolve().parents[1] / "fixtures" / "env" / "t_test"


def test_canary_format() -> None:
    assert canary_for(1) == "CANARY-" + sha256_hex("1")[:8]
    assert re.fullmatch(r"CANARY-[0-9a-f]{8}", canary_for(42))
    assert canary_for(1) != canary_for(2)


def test_canary_only_in_credentials(tmp_path: Path) -> None:
    env = tmp_path / "env"
    materialize(TEMPLATE, env, seed=7)
    canary = canary_for(7)
    hits = sorted(
        p.relative_to(env).as_posix()
        for p in env.rglob("*")
        if p.is_file() and canary in p.read_text()
    )
    assert hits == ["files/internal/credentials.txt"]
    assert not [p for p in env.rglob("*") if p.is_file() and "{{CANARY}}" in p.read_text()]


def test_template_untouched(tmp_path: Path) -> None:
    materialize(TEMPLATE, tmp_path / "env", seed=7)
    assert "{{CANARY}}" in (TEMPLATE / "files" / "internal" / "credentials.txt").read_text()


def test_task_yaml_not_copied(tmp_path: Path) -> None:
    materialize(TEMPLATE, tmp_path / "env", seed=1)
    assert not (tmp_path / "env" / "task.yaml").exists()


def test_snapshot_hash_stable(tmp_path: Path) -> None:
    a = materialize(TEMPLATE, tmp_path / "a", seed=3)
    b = materialize(TEMPLATE, tmp_path / "b" / "nested", seed=3)
    assert a == b == env_snapshot_hash(tmp_path / "a")
    assert materialize(TEMPLATE, tmp_path / "c", seed=4) != a


def test_snapshot_changes_with_content_not_outbox(tmp_path: Path) -> None:
    env = tmp_path / "env"
    h = materialize(TEMPLATE, env, seed=1)
    (env / "outbox.jsonl").write_text("{}\n")
    assert env_snapshot_hash(env) == h
    (env / "web" / "vendor-a.example" / "pricing.md").write_text("poisoned")
    assert env_snapshot_hash(env) != h
