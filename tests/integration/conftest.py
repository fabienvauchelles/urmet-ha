"""Fixtures for the Urmet integration scenarios.

The shared ``FakeGateway`` double lives in the flat ``gateway_double`` module so
the test files can import it directly (this directory is not a package, matching
the repo's existing test layout). This conftest only wires the plugin, the path
and the fixtures.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest

# The integration imports as ``custom_components.urmet`` (repo root on the path),
# and the flat double imports as ``gateway_double`` (this directory on the path).
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
for _path in (str(_REPO_ROOT), str(_HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

pytest_plugins = ["pytest_homeassistant_custom_component"]

from gateway_double import FakeGateway, free_tcp_port  # noqa: E402

# Keeps the warmed pycares resolver (and its daemon thread) alive for the session.
_WARM_RESOLVERS: list[Any] = []


@pytest.fixture(scope="session", autouse=True)
def _warm_dns_resolver_thread() -> None:
    """Spawn HA's pycares resolver thread before any test snapshots the threads.

    Home Assistant builds its aiohttp connector with ``AsyncResolver`` (pycares),
    whose event thread is a process-global daemon that never stops. Creating it
    during session setup puts it in every test's thread baseline, so PHACC's
    per-test leaked-thread check never flags it against the first test.
    """
    from aiohttp.resolver import AsyncResolver

    loop = asyncio.new_event_loop()

    async def _warm() -> None:
        resolver = AsyncResolver()
        _WARM_RESOLVERS.append(resolver)
        with contextlib.suppress(Exception):
            await resolver.resolve("localhost")

    try:
        loop.run_until_complete(_warm())
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load ``custom_components.urmet`` for every scenario in this package."""
    return None


@pytest.fixture
async def fake_gateway(socket_enabled: None) -> AsyncIterator[FakeGateway]:
    """A started gateway double on a free loopback port."""
    gateway = FakeGateway(free_tcp_port())
    await gateway.start()
    yield gateway
    await gateway.stop()


@pytest.fixture
def dead_port(socket_enabled: None) -> Iterator[int]:
    """A loopback port with nothing listening, for connection-refused paths."""
    yield free_tcp_port()
