"""Gate fixtures: one data directory per gate session."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.gates.harness import Lab


@pytest.fixture(scope="session")
def lab() -> Lab:
    """Gate data lives in `data/gates/stage<N>/` (or `MASTRACE_GATE_DATA`), so real-model
    runs, their cache and verdicts survive between gate sessions (ISSUE-028)."""
    import os

    from mastrace.settings import REPO_ROOT, Settings
    from tests.gates.harness import gate_stage

    root = Path(
        os.environ.get("MASTRACE_GATE_DATA")
        or REPO_ROOT / "data" / "gates" / f"stage{gate_stage()}"
    )
    return Lab(Settings(data_dir=root))
