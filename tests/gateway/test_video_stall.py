"""Scenario: the picture stops moving, and the plug is pulled on it.

A stalled reader here is not a lost picture, it is a stopped doorphone: the recorder
writes uncompressed frames from pjmedia's clock thread, which drives every call's
bridge, so a pipe nobody drains blocks the conversation. Noticing is not the point;
ending it is. The watchdog has two ways of finding out (a probe for a dead encoder,
a clock for one that never delivered) and two budgets so one does not kill the other
early (trap 13).

The last three scenarios are the generation counter (trap 15): the guard that a
stale ``PictureWait`` cannot arm a recorder onto a pipe a rebuild or a stall has
already killed. It refuses a moved generation before the crossing and after it, and
a wait that recorded the old generation never opens a tap on the new pipe.
"""

import pytest
from support import DEAD_EXIT_CODE, FakeVideoTap, eventually, stand_in_encoder
from urmet_sdk import VideoFormat

from urmet_gateway.media import picture_wait
from urmet_gateway.media.picture_wait import PictureWait
from urmet_gateway.media.pipeline import DownlinkNotStartedError, StaleArmError, VideoDownlink
from urmet_gateway.media.watchdog import Stall, Watchdog

BROAD_S = 30.0
TIGHT_S = 0.05


async def test_an_encoder_that_died_is_noticed_and_the_pipeline_is_released() -> None:
    """A dead encoder answers the probe at once, and the reaction pulls the plug."""
    stalls: list[Stall] = []

    async def record(stall: Stall) -> None:
        stalls.append(stall)

    downlink = VideoDownlink(FakeVideoTap(), on_stall=record, silence_timeout_s=BROAD_S)
    with stand_in_encoder(alive=False):
        try:
            await downlink.start()
            await eventually(lambda: stalls, timeout=5.0)
        finally:
            await downlink.aclose()

    assert len(stalls) == 1
    assert stalls[0].name == "video"
    assert stalls[0].reason == f"the encoder exited with {DEAD_EXIT_CODE}"
    # The pipeline was released, so there is nothing left for the recorder to fill.
    with pytest.raises(DownlinkNotStartedError):
        _ = downlink.pipe_path


async def test_a_pipeline_that_never_delivers_anything_is_given_up_on() -> None:
    """The other way the watchdog finds out: the startup budget, its own clock."""
    stalls: list[Stall] = []

    async def record(stall: Stall) -> None:
        stalls.append(stall)

    downlink = VideoDownlink(
        FakeVideoTap(), on_stall=record, silence_timeout_s=BROAD_S, startup_timeout_s=TIGHT_S
    )
    with stand_in_encoder(alive=True):
        try:
            await downlink.start()
            await eventually(lambda: stalls, timeout=5.0)
        finally:
            await downlink.aclose()

    assert len(stalls) == 1
    assert "nothing ever arrived" in stalls[0].reason
    assert stalls[0].silent_for_s > TIGHT_S


async def test_the_watchdog_has_two_budgets_and_rearm_restarts_the_coming_up_one() -> None:
    """The watchdog itself, driven fast and deterministically (trap 13).

    A coming-up budget the arming rearm restarts, so a stream tapped late is not
    killed a moment after it succeeded; and a running stream held to a tighter one.
    """
    stalls: list[Stall] = []

    async def record(stall: Stall) -> None:
        stalls.append(stall)

    wd = Watchdog(name="t", timeout_s=BROAD_S, startup_timeout_s=0.15, on_stall=record, poll_s=0.02)
    wd.start()
    try:
        await eventually_false(lambda: stalls, hold=0.1)
        wd.rearm()  # the tap took: start the coming-up budget again from here
        await eventually_false(lambda: stalls, hold=0.1)  # not killed just after success
        await eventually(lambda: stalls, timeout=1.0)
    finally:
        await wd.aclose()
    assert "nothing ever arrived" in stalls[0].reason


async def test_a_stale_arm_is_refused_before_the_crossing() -> None:
    """A generation that was never current is refused, and the tap is never touched."""
    tap = FakeVideoTap()
    downlink = VideoDownlink(tap)
    with stand_in_encoder(alive=True):
        try:
            await downlink.start()
            with pytest.raises(StaleArmError):
                await downlink.arm(downlink.generation - 1)
            assert tap.opens == []
        finally:
            await downlink.aclose()


async def test_a_stale_arm_racing_a_rebuild_is_refused_and_the_tap_is_closed() -> None:
    """A rebuild lands while the arm crosses: the post-check closes what it opened."""
    tap = FakeVideoTap()
    downlink = VideoDownlink(tap)
    with stand_in_encoder(alive=True):
        try:
            await downlink.start()
            generation = downlink.generation
            tap.during_open = downlink.restart  # the generation moves mid-crossing
            with pytest.raises(StaleArmError):
                await downlink.arm(generation)
            # What the arm opened on the now-dead pipe was closed, not left armed.
            assert tap.closes >= 1
            assert downlink.generation != generation
        finally:
            await downlink.aclose()


async def test_a_picture_wait_that_recorded_the_old_generation_never_arms(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """End to end (trap 15): the wait carries its generation into the arm, and a
    rebuild that moved it keeps the wait from ever opening a tap on the new pipe."""
    monkeypatch.setattr(picture_wait, "RETRY_INTERVAL_S", 0.01)
    tap = FakeVideoTap()
    downlink = VideoDownlink(tap)
    captured: list[int] = []
    arrived: list[VideoFormat] = []
    nevers: list[str] = []

    async def ask(generation: int) -> VideoFormat:
        captured.append(generation)
        return await downlink.arm(generation)

    async def on_never(reason: str) -> None:
        nevers.append(reason)

    wait = PictureWait(
        name="s", ask=ask, on_arrived=arrived.append, on_never=on_never, first_delay_s=0.0
    )
    with stand_in_encoder(alive=True):
        try:
            await downlink.start()
            stale = downlink.generation
            await downlink.restart()  # a rebuild moved the pipeline out from under it
            wait.start("waiting", generation=stale)
            await eventually(lambda: len(captured) >= 3, timeout=2.0)
            await wait.stop()
        finally:
            await downlink.aclose()

    assert captured and all(generation == stale for generation in captured)
    assert tap.opens == []  # never armed on the new pipe
    assert arrived == []
    assert nevers == []


async def eventually_false(predicate, *, hold: float) -> None:  # type: ignore[no-untyped-def]
    """Assert ``predicate`` stays falsy for ``hold`` seconds."""
    import asyncio

    loop = asyncio.get_running_loop()
    deadline = loop.time() + hold
    while loop.time() < deadline:
        assert not predicate(), "the watchdog fired inside the budget it was given"
        await asyncio.sleep(0.01)
