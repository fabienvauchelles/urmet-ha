"""The media tap, crossed on the one thread every SDK call crosses.

``MediaTap`` blocks and belongs to a single thread, the same one a REGISTER and
an open INFO go out on. A media session lives on the event loop and may not
block it, so it never holds that Protocol: it holds a ``WorkerTap``, which binds
one call handle, submits each crossing to the SDK worker, and awaits it.

Binding the handle here rather than passing it about is what keeps a session
from being able to name a call that is not its own. And ``open_video`` takes no
size argument, so no caller can pass one: the recorder cap is fixed here at a
value that stays inside the signed 32-bit field the native recorder narrows it
into, past which 4 GiB wraps to zero and the pipe closes before the first frame.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from urmet_sdk import AudioFormat, AudioSink, CallHandle, MediaTap, VideoFormat

from urmet_gateway.sip.worker import SdkWorker

# The recorder's ``max_size`` lands in a signed 32-bit field. 1.5 GiB is well
# inside it and nothing is ever stored: the "file" is only a few kilobytes in
# flight down a pipe. Passing 2**31 or more would wrap to zero and stop the
# recorder before its first write. (urmet-web trap 1, measured.)
MAX_TAP_BYTES: Final = 1536 * 1024 * 1024
assert 1 <= MAX_TAP_BYTES <= 2**31 - 1


class WorkerTap:
    """One call's media tap, awaited rather than called."""

    def __init__(self, tap: MediaTap, worker: SdkWorker, call: CallHandle) -> None:
        self._tap = tap
        self._worker = worker
        self._call = call

    async def open_video(self, sink_path: Path) -> VideoFormat:
        """Write the call's decoded video into ``sink_path``, and say at what size.

        The reader on ``sink_path`` must already be draining it: the native side
        refuses a pipe with no reader rather than blocking on ``open`` for one.
        """
        return await self._worker.run(
            self._tap.open_video_tap, self._call, sink_path, MAX_TAP_BYTES
        )

    async def close_video(self) -> None:
        """Stop writing and release the recorder. Idempotent, and safe once gone."""
        await self._worker.run(self._tap.close_video_tap, self._call)

    async def attach_audio(self, sink: AudioSink) -> AudioFormat:
        """Put ``sink`` in both directions of the call, and say in what PCM."""
        return await self._worker.run(self._tap.attach_audio_tap, self._call, sink)

    async def detach_audio(self) -> None:
        """Take the sink out and release the native port. Idempotent."""
        await self._worker.run(self._tap.detach_audio_tap, self._call)
