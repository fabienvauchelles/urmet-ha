"""One pipe, one ffmpeg and one demux thread: everything a rebuild replaces.

The recorder writes uncompressed frames into a named pipe; ffmpeg drains it and
re-encodes to H.264 in MPEG-TS on stdout; a thread demuxes that back into packets.
All three are one unit because the recorder fixes geometry in its header. The standby
read end is held until the demuxer proves ffmpeg is draining (trap 15), so arming
never blocks and a dead encoder blocks pjmedia rather than the recorder.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import IO, cast

import av
from av.packet import Packet
from av.video.stream import VideoStream

logger = logging.getLogger(__name__)

# -g 7 is one second of GOP at the panel's ~7 fps (its PLI cannot be honoured);
# force_key_frames makes the first frame an IDR so a browser waits no GOP (DESIGN 3.3).
KEYFRAME_INTERVAL = 7

PUMP_JOIN_S = 2.0
REAP_S = 5.0
FIFO_NAME = "tap.fifo"
LOG_NAME = "ffmpeg.log"
LOG_TAIL_LINES = 10
_PIPE_TOKEN = "{PIPE}"

# ffmpeg that ended cleanly, and ffmpeg we killed. Any other code logs its tail.
EXPECTED_EXITS = frozenset({0, -9})

# Same probing trap as ffmpeg's input, one layer up (trap 6): defaults probe 5 MB,
# ten more seconds unseen; the format is stated, so nothing needs discovering.
DEMUX_OPTIONS = {"fflags": "nobuffer", "probesize": "32768", "analyzeduration": "0"}

# ffmpeg's whole case (belongs in constants.py per trap 6; here until that lands):
# no B frames + zerolatency (one frame in, one packet out, in order); baseline for the
# browser; -probesize/-analyzeduration bound the probe (9.31 s -> 0.20 s); MPEG-TS is
# Annex B already (trap 7); flush_packets keeps the muxer honest.
ENCODER_TEMPLATE = (
    "ffmpeg -hide_banner -nostdin -loglevel error "
    "-fflags +nobuffer -probesize 32768 -analyzeduration 0 "
    f"-f avi -i {_PIPE_TOKEN} -an "
    "-c:v libx264 -preset veryfast -tune zerolatency -profile:v baseline "
    f"-pix_fmt yuv420p -bf 0 -g {KEYFRAME_INTERVAL} -force_key_frames expr:gte(t,0) "
    "-f mpegts -muxdelay 0 -muxpreload 0 -flush_packets 1 pipe:1"
)


def encoder_argv(pipe: Path) -> list[str]:
    """Build ffmpeg's argv, substituting the FIFO path after the split (no flag
    carries whitespace, so a path with spaces still survives)."""
    return [str(pipe) if token == _PIPE_TOKEN else token for token in ENCODER_TEMPLATE.split()]


class EncoderRun:
    """The pipe, the encoder and the demuxer for one geometry of one call."""

    def __init__(self, sink: Callable[[Packet[VideoStream]], None]) -> None:
        self._sink = sink
        self._workdir = Path(tempfile.mkdtemp(prefix="urmet-video-"))
        self._pipe = self._workdir / FIFO_NAME
        self._proc: subprocess.Popen[bytes] | None = None
        self._log: IO[bytes] | None = None
        self._pump: threading.Thread | None = None
        self._stopping = threading.Event()
        self._standby: int | None = None
        self._standby_lock = threading.Lock()
        self._draining = False

    @property
    def pipe_path(self) -> Path:
        """The named pipe the caller arms the video tap on."""
        return self._pipe

    @property
    def draining(self) -> bool:
        """A reader is on the pipe (trap 2): true from ``start`` until ``kill``."""
        return self._draining

    def start(self) -> None:
        """Make the pipe, hold its read end (this process, not ffmpeg), and start the
        encoder and demuxer. Nothing is read through the standby; ffmpeg's stderr goes
        to a file, never a pipe that would fill and block it (trap 16)."""
        os.mkfifo(self._pipe, 0o600)
        self._standby = os.open(self._pipe, os.O_RDONLY | os.O_NONBLOCK)
        self._log = (self._workdir / LOG_NAME).open("wb")
        self._proc = subprocess.Popen(
            encoder_argv(self._pipe),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=self._log,
        )
        self._pump = threading.Thread(
            target=self._demux,
            args=(cast(IO[bytes], self._proc.stdout),),
            name="urmet-video-demux",
            daemon=True,
        )
        self._pump.start()
        self._draining = True
        logger.info("video encoder up, waiting to be tapped on %s", self._pipe)

    def exit_code(self) -> int | None:
        """None while ffmpeg is alive. Read on every watchdog poll, never waits."""
        proc = self._proc
        return None if proc is None else proc.poll()

    def kill(self) -> None:
        """SIGKILL now, so the recorder's next write gets EPIPE not a blocked clock
        thread; the standby goes too, or the pipe still has a reader."""
        self._stopping.set()
        self._draining = False
        self._release_standby()
        proc = self._proc
        if proc is None:
            return
        with suppress(ProcessLookupError):
            proc.kill()

    def _release_standby(self) -> None:
        """Let go of the read end, once, safe from the demux thread or ``kill``."""
        with self._standby_lock:
            fd, self._standby = self._standby, None
        if fd is not None:
            os.close(fd)

    async def stop(self) -> None:
        """Kill the encoder, join the demuxer, reap the child, clear the pipe."""
        self.kill()
        proc, self._proc = self._proc, None
        if proc is not None:
            joined = await self._join_pump()
            await asyncio.to_thread(self._reap, proc, joined)
        self._clear_workdir()

    def _demux(self, stdout: IO[bytes]) -> None:
        """Turn the encoder's stream back into packets, on its own thread."""
        count = 0
        try:
            with av.open(stdout, mode="r", format="mpegts", options=DEMUX_OPTIONS) as container:
                # A header proves ffmpeg read the pipe: it is the sole reader now.
                self._release_standby()
                for packet in container.demux(container.streams.video[0]):
                    # demux ends on an empty flush packet; no decoder here to flush.
                    if self._stopping.is_set() or packet.size == 0:
                        break
                    self._sink(packet)
                    count += 1
        except Exception:
            if self._stopping.is_set():
                logger.debug("the video demuxer ended with its encoder, after %d packets", count)
                return
            logger.exception("the video demuxer stopped after %d packets", count)
            return
        logger.debug("the video demuxer ended after %d packets", count)

    async def _join_pump(self) -> bool:
        """Wait for the demux thread. It ends on the EOF the kill just caused."""
        pump, self._pump = self._pump, None
        if pump is None:
            return True
        await asyncio.to_thread(pump.join, PUMP_JOIN_S)
        if pump.is_alive():
            logger.warning("the video demux thread outlived its encoder; left to end alone")
            return False
        return True

    def _reap(self, proc: subprocess.Popen[bytes], joined: bool) -> None:
        """Collect the child and read its log out when it died on its own."""
        try:
            code = proc.wait(timeout=REAP_S)
        except subprocess.TimeoutExpired:
            logger.error("the encoder did not exit within %.0fs of being killed", REAP_S)
            return
        if code not in EXPECTED_EXITS:
            logger.error("the encoder exited with %d\n%s", code, self._log_tail())
        log, self._log = self._log, None
        if log is not None:
            log.close()
        # Closing a pipe another thread may still read is a use after free (trap 17).
        if joined and proc.stdout is not None:
            proc.stdout.close()

    def _log_tail(self) -> str:
        try:
            lines = (self._workdir / LOG_NAME).read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            return f"(its log could not be read: {error})"
        return "\n".join(lines.splitlines()[-LOG_TAIL_LINES:])

    def _clear_workdir(self) -> None:
        if not self._workdir.exists():
            return
        try:
            shutil.rmtree(self._workdir)
        except OSError as error:
            logger.warning("the video work directory %s was left behind: %s", self._workdir, error)
