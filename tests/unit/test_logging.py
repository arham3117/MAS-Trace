"""P0.5: logging and code version."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

import pytest

from mastrace.core.logging import code_version, get_logger, setup_logging


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("one\n")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_clean_repo_gives_short_hash(repo: Path) -> None:
    v = code_version(repo)
    assert re.fullmatch(r"[0-9a-f]{7,}", v)


def test_modified_file_is_dirty(repo: Path) -> None:
    clean = code_version(repo)
    (repo / "a.txt").write_text("two\n")
    assert code_version(repo) == f"{clean}-dirty"


def test_untracked_file_is_dirty(repo: Path) -> None:
    (repo / "new.py").write_text("x = 1\n")
    assert code_version(repo).endswith("-dirty")


def test_new_commit_changes_hash(repo: Path) -> None:
    first = code_version(repo)
    (repo / "a.txt").write_text("two\n")
    _git(repo, "commit", "-q", "-am", "second")
    second = code_version(repo)
    assert second != first
    assert not second.endswith("-dirty")


def test_not_a_repo(tmp_path: Path) -> None:
    assert code_version(tmp_path) == "unknown"


def test_setup_logging_writes_file(tmp_path: Path) -> None:
    logger = setup_logging(log_dir=tmp_path)
    get_logger("test").info("hello log")
    for h in logger.handlers:
        h.flush()
    assert "hello log" in (tmp_path / "mastrace.log").read_text()


def test_setup_logging_is_idempotent(tmp_path: Path) -> None:
    setup_logging(log_dir=tmp_path)
    logger = setup_logging(log_dir=tmp_path, level=logging.DEBUG)
    assert len(logger.handlers) == 2
    assert logger.level == logging.DEBUG
