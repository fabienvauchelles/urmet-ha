"""The single snapshot of what the interface draws.

State and counters are the same reading, built in one place so they cannot drift:
the live dialogs come from the call book, the flowing media from the sessions,
and the binding from the port. It is read without crossing the SDK worker thread,
on purpose: a snapshot queued behind a blocking view would reach the browser long
after the doorbell it describes.
"""

from __future__ import annotations

from collections.abc import Callable

from urmet_gateway.domain.models import CallView, DoorphoneView, SessionView, StateView
from urmet_gateway.domain.ports import DoorphonePort


class StateReader:
    """Assembles the one snapshot every reader and every event is made of."""

    def __init__(
        self,
        *,
        port: DoorphonePort,
        calls_views: Callable[[], list[CallView]],
        sessions_views: Callable[[], list[SessionView]],
        mic_muted: Callable[[], bool],
    ) -> None:
        self._port = port
        self._calls_views = calls_views
        self._sessions_views = sessions_views
        self._mic_muted = mic_muted

    def snapshot(self) -> StateView:
        """A reading of the binding, the live dialogs and the flowing media."""
        doorphone = self._port.known_doorphone()
        return StateView(
            registered=self._port.registered,
            doorphone=DoorphoneView.of(doorphone) if doorphone is not None else None,
            calls=self._calls_views(),
            mic_muted=self._mic_muted(),
            sessions=self._sessions_views(),
        )
