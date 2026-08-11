"""Test isolation guard.

Refuses the two things a full-scenario suite must never do: import the native
``pjsua2`` binding, or connect a socket to a non-loopback address. Both raise
``IsolationViolation`` (a ``BaseException`` subclass) so a violation fails the run
rather than being caught by the gateway's ``Exception`` middleware.
"""

from __future__ import annotations

import ipaddress
import socket
import sys
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Any

_BANNED_ROOT_MODULES = frozenset({"pjsua2"})
_LOOPBACK_HOSTNAMES = frozenset({"localhost", ""})


class IsolationViolation(BaseException):
    """A test tried to reach the native stack or a non-loopback network peer."""


class _NativeBindingBlocker(MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: Any = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        if fullname.split(".", 1)[0] in _BANNED_ROOT_MODULES:
            raise IsolationViolation(
                f"import of {fullname!r} is forbidden in the test suite: "
                "no test may touch the native pjsua2 binding"
            )
        return None


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in _LOOPBACK_HOSTNAMES


def _reject_non_loopback(family: int, address: Any) -> None:
    if family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple):
        host = str(address[0])
        if not _is_loopback(host):
            raise IsolationViolation(
                f"connection to non-loopback address {host!r} is forbidden in the "
                "test suite: no test may open the network"
            )


_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_sendto = socket.socket.sendto
_installed = False


def _guarded_connect(self: socket.socket, address: Any) -> None:
    _reject_non_loopback(self.family, address)
    return _real_connect(self, address)


def _guarded_connect_ex(self: socket.socket, address: Any) -> int:
    _reject_non_loopback(self.family, address)
    return _real_connect_ex(self, address)


def _guarded_sendto(self: socket.socket, data: Any, *args: Any) -> int:
    if args:
        _reject_non_loopback(self.family, args[-1])
    return _real_sendto(self, data, *args)


def install() -> None:
    """Install the import blocker and the socket guard. Idempotent."""
    global _installed
    if _installed:
        return
    sys.meta_path.insert(0, _NativeBindingBlocker())
    socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _guarded_connect_ex  # type: ignore[method-assign]
    socket.socket.sendto = _guarded_sendto  # type: ignore[method-assign]
    _installed = True
