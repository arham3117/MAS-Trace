"""P0.4: test fixtures."""

from __future__ import annotations

import os
import random
import socket
import tempfile
import urllib.request
from pathlib import Path

import pytest

from mastrace.settings import get_settings
from tests.netguard import NetworkBlockedError, NetworkGuard


def test_outbound_connection_raises_inside_no_network(no_network: NetworkGuard) -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s,
        pytest.raises(NetworkBlockedError),
    ):
        s.connect(("203.0.113.1", 80))  # TEST-NET-3, never routable
    assert no_network.blocked == [("203.0.113.1", 80)]


def test_connect_ex_is_blocked_too() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s,
        pytest.raises(NetworkBlockedError),
    ):
        s.connect_ex(("203.0.113.1", 80))


def test_http_library_is_blocked() -> None:
    with pytest.raises(Exception, match="no_network"):
        urllib.request.urlopen("http://203.0.113.1/", timeout=1)


def test_localhost_blocked_when_not_a_model_host() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s,
        pytest.raises(NetworkBlockedError),
    ):
        s.connect(("127.0.0.1", 9))


def test_allowed_host_is_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A host on the allowlist (model hosts, in `model` tests) is reachable."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        guard = NetworkGuard({"127.0.0.1"})
        monkeypatch.setattr(socket.socket, "connect", guard.wrap_connect())
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.connect(server.getsockname())
        assert guard.blocked == []


def test_unix_sockets_not_blocked() -> None:
    # Short dir: macOS caps AF_UNIX paths at 104 bytes, and pytest's tmp_path is longer.
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        path = os.path.join(d, "s.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(path)
            server.listen(1)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(path)


def test_tmp_data_dir(tmp_data_dir: Path) -> None:
    assert tmp_data_dir.is_dir()
    assert get_settings().data_dir == tmp_data_dir


def test_fixed_seed_is_deterministic(fixed_seed: int) -> None:
    first = random.random()
    random.seed(fixed_seed)
    assert random.random() == first
