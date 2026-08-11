"""The registration supervisor: backoff cadence, deferral, and honest release.

The supervisor is driven through its public surface (``start`` and ``stop``) with
its clock and its client factory injected, so the measured reconnect cadence is
asserted without a single real second of waiting. The client it drives is a
controllable stand-in for the SDK client: it raises the SDK's own
``RegistrationError`` to fail a REGISTER and answers ``stop`` with a release the
registrar did or did not confirm. pjsua2 is never imported.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest
from urmet_sdk import CallHandle, CallState, Doorphone, RegistrationError, RingEvent

from urmet_gateway.sip import CallbackBridge, RegistrationSupervisor, SdkWorker


class _FakeClient:
    """A stand-in ``SupervisedClient``: a scripted REGISTER and release."""

    def __init__(self, *, fail_start: bool, stop_result: bool = True) -> None:
        self._fail_start = fail_start
        self._stop_result = stop_result
        self._registered = False
        self._status = 0
        self._reason = ""

    def start(self, *, timeout: float | None = None) -> None:
        if self._fail_start:
            self._status, self._reason = 403, "Forbidden"
            raise RegistrationError("start: REGISTER rejected with 403 Forbidden")
        self._registered, self._status, self._reason = True, 200, "OK"

    def stop(self) -> bool:
        self._registered = False
        return self._stop_result

    @property
    def registered(self) -> bool:
        return self._registered

    @property
    def registration_status_code(self) -> int:
        return self._status

    @property
    def registration_reason(self) -> str:
        return self._reason


@pytest.mark.asyncio
async def test_reconnect_follows_the_measured_backoff_cadence() -> None:
    worker = SdkWorker()
    sleeps: list[float] = []
    holder: dict[str, RegistrationSupervisor] = {}

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) >= 6:
            holder["s"]._stopped = True
        await asyncio.sleep(0)

    supervisor = RegistrationSupervisor(
        build_client=lambda: _FakeClient(fail_start=True),
        worker=worker,
        publish=lambda _o: None,
        sleep=fake_sleep,
    )
    holder["s"] = supervisor

    await supervisor.start()
    task = supervisor._task
    assert task is not None
    await asyncio.wait_for(task, timeout=5.0)

    assert sleeps == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0]
    await worker.aclose()


@pytest.mark.asyncio
async def test_a_deferred_retry_does_not_advance_the_backoff() -> None:
    worker = SdkWorker()
    sleeps: list[float] = []
    holder: dict[str, RegistrationSupervisor] = {}
    busy_calls = [0]

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) >= 3:
            holder["s"]._stopped = True
        await asyncio.sleep(0)

    def is_busy() -> bool:
        # Busy on the very first check only: one retry is deferred, and the
        # backoff must stay where it is because nothing was tried.
        busy_calls[0] += 1
        return busy_calls[0] == 1

    supervisor = RegistrationSupervisor(
        build_client=lambda: _FakeClient(fail_start=True),
        worker=worker,
        publish=lambda _o: None,
        sleep=fake_sleep,
        is_busy=is_busy,
    )
    holder["s"] = supervisor

    await supervisor.start()
    task = supervisor._task
    assert task is not None
    await asyncio.wait_for(task, timeout=5.0)

    # The first delay repeats (5, then 5 again for the deferral) before it
    # advances to 10, rather than jumping straight to 10 on the second wake.
    assert sleeps == [5.0, 5.0, 10.0]
    await worker.aclose()


class _RecordingClient:
    """A stand-in that is also a doorbell source, so the bridge can bind to it."""

    def __init__(self, *, fail_start: bool) -> None:
        self._fail_start = fail_start
        self._registered = False
        self.ring_cb: Callable[[RingEvent], None] | None = None
        self.call_cb: Callable[[CallHandle, CallState], None] | None = None

    def start(self, *, timeout: float | None = None) -> None:
        if self._fail_start:
            raise RegistrationError("start: REGISTER rejected with 503 Service Unavailable")
        self._registered = True

    def stop(self) -> bool:
        self._registered = False
        return True

    @property
    def registered(self) -> bool:
        return self._registered

    @property
    def registration_status_code(self) -> int:
        return 200 if self._registered else 0

    @property
    def registration_reason(self) -> str:
        return "OK" if self._registered else ""

    def on_ring(self, cb: Callable[[RingEvent], None]) -> None:
        self.ring_cb = cb

    def on_call_state(self, cb: Callable[[CallHandle, CallState], None]) -> None:
        self.call_cb = cb

    @property
    def bound(self) -> bool:
        return self.ring_cb is not None and self.call_cb is not None


@pytest.mark.asyncio
async def test_a_reconnection_rebuilds_the_client_and_resubscribes_the_callbacks() -> None:
    loop = asyncio.get_running_loop()
    worker = SdkWorker()
    rings: list[RingEvent] = []
    bridge = CallbackBridge(loop=loop, on_ring=rings.append, on_call=lambda _c, _s: None)

    first = _RecordingClient(fail_start=True)
    second = _RecordingClient(fail_start=False)
    built: list[_RecordingClient] = []

    def build_client() -> _RecordingClient:
        # The first REGISTER is refused, so the supervisor rebuilds; every later
        # build gets the client that accepts. The factory wires each new client the
        # way the composition root does: bind the bridge, so a rebuild re-subscribes.
        client = first if not built else second
        bridge.bind(client)
        built.append(client)
        return client

    up = asyncio.Event()

    def publish(outcome: object) -> None:
        if getattr(outcome, "registered", False):
            up.set()

    async def fast_sleep(_delay: float) -> None:
        await asyncio.sleep(0)

    supervisor = RegistrationSupervisor(
        build_client=build_client,
        worker=worker,
        publish=publish,
        sleep=fast_sleep,
    )

    await supervisor.start()
    await asyncio.wait_for(up.wait(), timeout=5.0)

    # The refused first client was thrown away and a fresh one was built and
    # registered (asserted before ``stop``, whose release clears the flag).
    assert len(built) == 2
    assert built[0] is first
    assert built[1] is second
    assert second.registered is True

    # The callbacks were re-subscribed onto the new client: a ring fired on it
    # reaches the loop-side handler through the bridge, proving the bind took.
    assert second.bound
    assert second.ring_cb is not None
    door = Doorphone(mac="00:11:22:33:44:55", name="Front Gate")
    second.ring_cb(RingEvent(doorphone=door, call_id="c1"))
    for _ in range(5):
        await asyncio.sleep(0)
    assert [event.call_id for event in rings] == ["c1"]

    await supervisor.stop()
    await worker.aclose()


@pytest.mark.asyncio
async def test_an_unconfirmed_release_is_published() -> None:
    worker = SdkWorker()
    outcomes = []
    registered = asyncio.Event()

    def publish(outcome: object) -> None:
        outcomes.append(outcome)
        if getattr(outcome, "registered", False):
            registered.set()

    supervisor = RegistrationSupervisor(
        build_client=lambda: _FakeClient(fail_start=False, stop_result=False),
        worker=worker,
        publish=publish,
        liveness_interval_s=1000.0,
    )

    await supervisor.start()
    await asyncio.wait_for(registered.wait(), timeout=2.0)
    await supervisor.stop()

    assert any(o.registered for o in outcomes)
    last = outcomes[-1]
    assert last.registered is False
    assert last.released is False
    assert "expire" in last.reason
    await worker.aclose()
