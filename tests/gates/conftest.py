"""Gate fixtures: one data directory per gate session."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.gates.harness import Lab


@pytest.fixture(scope="session")
def lab(tmp_path_factory: pytest.TempPathFactory) -> Lab:
    from mastrace.settings import Settings

    root: Path = tmp_path_factory.mktemp("gate")
    return Lab(Settings(data_dir=root / "data"))
