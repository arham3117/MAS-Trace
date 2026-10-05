"""Logging setup and the code version stamped on every event."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

LOGGER_NAME = "mastrace"
LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: int | str = logging.INFO, log_dir: Path | None = None) -> logging.Logger:
    """Configure the `mastrace` logger to write to `<log_dir>/mastrace.log` and the console.

    Calling it again replaces the handlers, so it is safe to call more than once.
    """
    log_dir = log_dir if log_dir is not None else Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    fmt = logging.Formatter(LOG_FORMAT)
    file_handler = logging.FileHandler(log_dir / "mastrace.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(console)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child of the `mastrace` logger, e.g. `get_logger("router")`."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def code_version(repo: Path | None = None) -> str:
    """Git short hash of HEAD, plus `-dirty` if the work tree has uncommitted changes.

    Untracked (non-ignored) files count as changes, because they can change behaviour.
    Returns `"unknown"` outside a git repo or before the first commit.
    """
    cwd = repo if repo is not None else Path(__file__).resolve().parent
    try:
        short = _git(["rev-parse", "--short", "HEAD"], cwd)
        dirty = _git(["status", "--porcelain"], cwd) != ""
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    return f"{short}-dirty" if dirty else short
