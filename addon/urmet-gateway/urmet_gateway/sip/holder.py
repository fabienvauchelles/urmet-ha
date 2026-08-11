"""The one place that names the client every command speaks through right now.

The registration supervisor owns the client's whole lifecycle, and ``stop()`` is
terminal, so a lost binding is recovered by building a new client over a new
transport rather than restarting the old one. Every command path (view, answer,
open, mic) must therefore reach the current client, not one captured at boot and
left pointing at a dead stack after the first reconnect.

This holder is that indirection. The client factory updates it on every build,
and the SIP port resolves through ``current`` on every command, so a rebuild is
invisible to everyone but the supervisor that caused it.
"""

from __future__ import annotations

from collections.abc import Callable

from urmet_gateway.domain.errors import NoClientError


def rebuilding_factory[T](build: Callable[[], T]) -> Callable[[], T]:
    """Hand the eagerly built client back once, then a fresh build on every rebuild.

    The composition root builds and wires the first client at once, so the command
    path is warm before the port opens and no read races an empty holder. The
    supervisor then reuses that first client for the boot REGISTER (there is never
    a second client at boot) and gets a genuinely fresh one only when it rebuilds
    after a lost binding.
    """
    pending: list[T] = [build()]

    def factory() -> T:
        if pending:
            return pending.pop()
        return build()

    return factory


class ClientHolder[T]:
    """Holds the client currently in use, swapped whole by the factory on rebuild."""

    def __init__(self) -> None:
        self._client: T | None = None

    def set(self, client: T) -> None:
        """Point every later ``current`` at ``client``. Called on each build."""
        self._client = client

    def current(self) -> T:
        """The client in use now, or ``NoClientError`` before the first build."""
        if self._client is None:
            raise NoClientError("no SIP client has been built yet")
        return self._client
