"""The dialogs the gateway is watching, and which side started them.

The SDK keeps a registry of its own for the waits it performs, and it is not
this one. This book exists because the interface has to list what is up, with two
things the SDK never hands out: the direction of each dialog, and the handle an
HTTP request naming a call id has to be turned back into.

The one rule that is not negotiable: only the transport says a dialog exists. A
command may sharpen an entry the transport put here, never put one back. A dialog
can end while the command that opened it is still awaiting the SDK; the terminal
state reaches the loop first and the entry is dropped, and an entry written after
it would never be dropped again, because no further callback carries that id.
"""

from __future__ import annotations

from dataclasses import dataclass

from urmet_sdk import CallHandle, CallState

from urmet_gateway.domain.errors import UnknownCallError
from urmet_gateway.domain.models import CallView, Direction


@dataclass
class TrackedCall:
    """One dialog: the handle to act on it, where it stands, who started it."""

    handle: CallHandle
    state: CallState
    direction: Direction


class CallBook:
    """The live dialogs, by call id, in the order they appeared."""

    def __init__(self) -> None:
        self._calls: dict[str, TrackedCall] = {}
        # Ids the panel rang us on. Kept apart from the entries because the
        # transport may report a state for an inbound dialog before the ring
        # itself reaches the loop, and a dialog never changes sides afterwards.
        self._rang: set[str] = set()

    def record(
        self,
        handle: CallHandle,
        state: CallState,
        direction: Direction,
        *,
        refine_only: bool = False,
    ) -> bool:
        """Store a reported state and answer whether it is new information.

        ``refine_only`` True never creates an entry: it is what a command uses,
        because the transport is the only thing that says a dialog exists.
        ``direction`` is the caller's guess from what it was doing; a ring
        already seen for this id overrules it. False means nothing was learned,
        which a state reported twice and a command describing a gone dialog both
        are.
        """
        side = Direction.INCOMING if handle.id in self._rang else direction
        tracked = self._calls.get(handle.id)
        if tracked is None:
            if refine_only:
                return False
            self._calls[handle.id] = TrackedCall(handle=handle, state=state, direction=side)
            return True
        tracked.handle = handle
        tracked.direction = side
        if tracked.state is state:
            return False
        tracked.state = state
        return True

    def mark_incoming(self, call_id: str) -> None:
        """Record that the panel rang us on ``call_id``, whatever was assumed."""
        self._rang.add(call_id)
        tracked = self._calls.get(call_id)
        if tracked is not None:
            tracked.direction = Direction.INCOMING

    def find(self, call_id: str) -> TrackedCall | None:
        """The entry for ``call_id``, or None when no such dialog is up."""
        return self._calls.get(call_id)

    def require(self, call_id: str) -> TrackedCall:
        """The entry for ``call_id``, or ``UnknownCallError`` when none is up.

        The single source of the unknown-call message: ``handle`` and every
        caller that needs the entry itself raise the same error through here.
        """
        tracked = self._calls.get(call_id)
        if tracked is None:
            raise UnknownCallError(f"unknown call {call_id}: it already ended or never started")
        return tracked

    def handle(self, call_id: str) -> CallHandle:
        """The handle to act on ``call_id``. Raises ``UnknownCallError``."""
        return self.require(call_id).handle

    def forget(self, call_id: str) -> None:
        """Drop a dialog that is over, freeing its id for the next one."""
        self._calls.pop(call_id, None)
        self._rang.discard(call_id)

    def clear(self) -> None:
        """Forget every dialog, after the stack has been torn down."""
        self._calls.clear()
        self._rang.clear()

    def streaming(self) -> list[TrackedCall]:
        """The dialogs whose media is up, in the order they appeared."""
        return [c for c in self._calls.values() if c.state.is_streaming]

    def views(self) -> list[CallView]:
        """What the interface shows: one entry per dialog still up."""
        return [
            CallView(id=call_id, state=c.state, direction=c.direction)
            for call_id, c in self._calls.items()
        ]
