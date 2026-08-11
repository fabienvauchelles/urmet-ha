"""Skeleton scenarios: the package tree imports and the isolation guard bites.

These keep the suite non-empty and green on the empty tree, and they prove the
two guarantees WP0 owns: every gateway package is importable, and the guard
refuses the native binding and the network.
"""

from __future__ import annotations

import importlib
import socket

import pytest

import isolation

GATEWAY_PACKAGES = [
    "urmet_gateway",
    "urmet_gateway.domain",
    "urmet_gateway.usecases",
    "urmet_gateway.sip",
    "urmet_gateway.media",
    "urmet_gateway.media.audio",
    "urmet_gateway.http",
]


@pytest.mark.parametrize("name", GATEWAY_PACKAGES)
def test_gateway_package_imports(name: str) -> None:
    module = importlib.import_module(name)
    assert module is not None


def test_pjsua2_import_is_refused() -> None:
    with pytest.raises(isolation.IsolationViolation):
        importlib.import_module("pjsua2")


def test_non_loopback_socket_is_refused() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        pytest.raises(isolation.IsolationViolation),
    ):
        sock.connect(("8.8.8.8", 53))
