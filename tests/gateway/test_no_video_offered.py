"""Scenario: a dialog that carries no video line at all, and one that comes up late.

``NoVideoOfferedError`` is its own type precisely so a caller does not loop for a
picture that can never arrive (trap 14). ``PictureWait`` treats it as terminal: it
stops asking and reports the reason, so a page is not shown "still coming" for ever.
Every other ``CallError`` is a picture that is merely late, and is retried until it
appears, which is how a stream the panel brings up after the answer is picked up.
"""

from support import eventually
from urmet_sdk import CallError, NoVideoOfferedError, VideoFormat

from urmet_gateway.media import picture_wait
from urmet_gateway.media.picture_wait import PictureWait

NO_VIDEO = "call 1 was placed without video, so there is none to tap"
NO_STREAM_YET = "call 1 carries no video stream to tap"
FORMAT = VideoFormat(width=320, height=240)


async def test_no_video_offered_ends_the_asking_for_good() -> None:
    arrived: list[VideoFormat] = []
    nevers: list[str] = []

    async def ask(_generation: int) -> VideoFormat:
        raise NoVideoOfferedError(NO_VIDEO)

    async def on_never(reason: str) -> None:
        nevers.append(reason)

    wait = PictureWait(
        name="s", ask=ask, on_arrived=arrived.append, on_never=on_never, first_delay_s=0.0
    )
    wait.start("waiting", generation=1)
    await eventually(lambda: nevers, timeout=2.0)

    assert nevers == [NO_VIDEO]
    assert arrived == []
    assert not wait.waiting


async def test_a_stream_that_comes_up_late_is_retried_until_it_arrives(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(picture_wait, "RETRY_INTERVAL_S", 0.01)
    attempts = 0
    arrived: list[VideoFormat] = []
    nevers: list[str] = []

    async def ask(_generation: int) -> VideoFormat:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise CallError(NO_STREAM_YET)
        return FORMAT

    async def on_never(reason: str) -> None:
        nevers.append(reason)

    wait = PictureWait(
        name="s", ask=ask, on_arrived=arrived.append, on_never=on_never, first_delay_s=0.0
    )
    wait.start("waiting", generation=1)
    await eventually(lambda: arrived, timeout=2.0)

    assert attempts >= 3
    assert arrived == [FORMAT]
    assert nevers == []
    assert not wait.waiting
    assert wait.reason == ""
