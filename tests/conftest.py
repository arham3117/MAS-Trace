"""Shared pytest fixtures (plan.md P0.4)."""

from __future__ import annotations

import random
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest

from mastrace.settings import allowed_model_hosts, get_settings
from tests.netguard import NetworkGuard

FIXED_SEED = 1234


@pytest.fixture(autouse=True)
def no_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> NetworkGuard:
    """Block outbound connections in every test.

    Tests marked `model` may additionally reach the provider hosts in `configs/models.yaml`;
    nothing else is ever reachable.
    """
    allowed: set[str] = set()
    if request.node.get_closest_marker("model") is not None:
        allowed = allowed_model_hosts()
    guard = NetworkGuard(allowed)
    monkeypatch.setattr(socket.socket, "connect", guard.wrap_connect())
    monkeypatch.setattr(socket.socket, "connect_ex", guard.wrap_connect_ex())
    return guard


@pytest.fixture
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point `Settings.data_dir` at a fresh temporary directory for this test."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("MASTRACE_DATA_DIR", str(data))
    get_settings.cache_clear()
    yield data
    get_settings.cache_clear()


@pytest.fixture
def fixed_seed() -> int:
    """Seed Python's (and numpy's, if present) RNG and return the seed."""
    random.seed(FIXED_SEED)
    try:
        import numpy as np

        np.random.seed(FIXED_SEED)
    except ImportError:
        pass
    return FIXED_SEED
