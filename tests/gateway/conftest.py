"""Shared fixtures and path setup for the gateway scenarios.

Two work packages share this directory with different import habits. The sip and
use-case tests import the harness helpers relatively (this is a package), while
the video tests import a flat ``support`` module; the ``sys.path`` line below
serves the second without disturbing the first. The ``harness`` fixture hands a
scenario the doubles and a cold client for the layers that want one; the
use-case tests build their own graph and need no fixture at all.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from .harness import Harness, HarnessFactory, build_harness

# The video scenarios import a flat ``support`` module rather than relatively, so
# their own directory goes on the path the way the root ``tests`` directory is.
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
async def make_harness() -> AsyncIterator[HarnessFactory]:
    """Factory for a scenario that needs a specific failure armed, or two graphs."""
    built: list[Harness] = []

    def factory(**overrides: Any) -> Harness:
        harness = build_harness(**overrides)
        built.append(harness)
        return harness

    yield factory
    for harness in reversed(built):
        harness.transport.shutdown()


@pytest.fixture
async def harness(make_harness: HarnessFactory) -> Harness:
    """A cold graph: doubles wired, a configured doorphone, nothing started yet."""
    return make_harness()
