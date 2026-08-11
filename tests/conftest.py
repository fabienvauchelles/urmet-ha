"""Shared pytest fixtures and the always-on isolation guard.

Importing this module installs the guard (``isolation.install()``), so every
test session refuses ``import pjsua2`` and every non-loopback socket before a
single test is collected. Async tests run under pytest-asyncio in ``auto`` mode
(configured in the root ``pyproject.toml``); no per-test loop plumbing is needed.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

import isolation

isolation.install()


@pytest.fixture(autouse=True, scope="session")
def _isolation_guard_active() -> Iterator[None]:
    """Fail loudly if the guard was somehow torn down before a session ran."""
    assert isolation._installed, "the isolation guard is not installed"
    yield
