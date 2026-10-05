"""Socket-level network guard used by the `no_network` fixture (plan.md P0.4, I1, G-C5)."""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterable
from typing import Any

_ORIGINAL_CONNECT = socket.socket.connect
_ORIGINAL_CONNECT_EX = socket.socket.connect_ex


class NetworkBlockedError(RuntimeError):
    """Raised when code under test opens a connection that is not allowed."""


def _resolve(hosts: Iterable[str]) -> set[str]:
    """Return the hostnames plus every IP address they resolve to."""
    out: set[str] = set()
    for host in hosts:
        out.add(host)
        try:
            for info in socket.getaddrinfo(host, None):
                out.add(str(info[4][0]))
        except OSError:
            pass
    return out


class NetworkGuard:
    """Replace `socket.socket.connect`/`connect_ex` with a check against an allowlist."""

    def __init__(self, allowed_hosts: Iterable[str] = ()) -> None:
        self.allowed = _resolve(sorted(allowed_hosts))
        self.blocked: list[Any] = []

    def _check(self, sock: socket.socket, address: Any) -> None:
        if sock.family == getattr(socket, "AF_UNIX", None):
            return  # local IPC, not network
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in self.allowed:
            self.blocked.append(address)
            raise NetworkBlockedError(f"no_network: outbound connection to {address!r} blocked")

    def wrap_connect(self) -> Callable[[socket.socket, Any], None]:
        """Build the replacement for `socket.socket.connect`."""

        def connect(sock: socket.socket, address: Any) -> None:
            self._check(sock, address)
            _ORIGINAL_CONNECT(sock, address)

        return connect

    def wrap_connect_ex(self) -> Callable[[socket.socket, Any], int]:
        """Build the replacement for `socket.socket.connect_ex`."""

        def connect_ex(sock: socket.socket, address: Any) -> int:
            self._check(sock, address)
            return _ORIGINAL_CONNECT_EX(sock, address)

        return connect_ex
