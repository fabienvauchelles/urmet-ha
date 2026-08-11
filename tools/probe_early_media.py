#!/usr/bin/env python3
"""Settle one question on real hardware, by hand: can the visitor be seen or
heard without ever sending 200 OK.

This is the experiment of DESIGN section 1.4 (see also EARLY-MEDIA-VERDICT.md),
deliberately NOT part of the gateway or the test suite. It answers one inbound
ring with ``183 Session Progress`` carrying an SDP answer, which the SDK never
sends, counts received video RTP for a fixed window, and declines without ever
answering. The full procedure and how to read the result live in
docs/hardware-test-plan.md, item 2. Run it attended, in daylight, never at night.

Guards: refuses to run without ``--yes-really-ring``; refuses any actuator command
(no actuator code path exists, actuator tokens on argv abort it); prints the
release outcome. It never sends Signal=1/2 or 200 OK, declining 486 (never 603).
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from _probe_common import (
    configure_logging,
    load_settings,
    provision_credentials,
    refuse_actuators,
    system_ca_bundle,
    timestamped_log_file,
)

from urmet_sdk import Settings, doorphone_from_uri
from urmet_sdk.sip.pjsip_account import build_acc_config
from urmet_sdk.sip.pjsip_binding import contained, load_pjsua2
from urmet_sdk.sip.pjsip_calls import NO_STREAM
from urmet_sdk.sip.pjsip_media_config import configure_codecs, configure_media, select_audio_device
from urmet_sdk.sip.pjsip_stack import USER_AGENT
from urmet_sdk.sip.pjsip_streams import read_media
from urmet_sdk.sip.pjsip_video import resolve_devices

log = configure_logging("probe_early_media")

# The one provisional the probe sends: the only response that could carry early
# media without cancelling the other ringing branches.
PROGRESS_CODE = 183
# 486 declines our branch and (RFC 3261 16.7) leaves the household handsets
# ringing. 603 would ask a conforming proxy to cancel every branch, so it is
# NEVER sent here. See DESIGN section 12 risk 4.
DECLINE_CODE = 486
DEFAULT_WINDOW_S = 20
DEFAULT_RING_WAIT_S = 300.0
PJSIP_WIRE_LEVEL = 5  # full SIP message dump; the compile ceiling. Never 6, it floods.
SAMPLE_INTERVAL_S = 1.0
RELEASE_BUDGET_S = 5.0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="probe_early_media",
        description="Answer one ring with 183 and measure early media. Attended only.",
    )
    parser.add_argument(
        "--yes-really-ring", action="store_true", help="required: a person is at the gate to press"
    )
    parser.add_argument("--seconds", type=int, default=DEFAULT_WINDOW_S, help="RTP count window")
    parser.add_argument("--ring-timeout", type=float, default=DEFAULT_RING_WAIT_S)
    parser.add_argument("--log-dir", type=Path, default=Path("logs"))
    return parser.parse_args(argv)


def _bring_up_endpoint(pj: Any, settings: Settings, log_file: Path) -> tuple[Any, int]:
    """Create the pjsua2 endpoint with the full SIP dump at level 5 to a file."""
    ep = pj.Endpoint()
    ep.libCreate()
    cfg = pj.EpConfig()
    cfg.logConfig.level = PJSIP_WIRE_LEVEL
    cfg.logConfig.consoleLevel = 1  # keep stdout for the probe's own progress lines
    cfg.logConfig.msgLogging = True  # whole SIP messages, so the 183+SDP is on the dump
    cfg.logConfig.filename = str(log_file)
    cfg.uaConfig.userAgent = USER_AGENT
    configure_media(cfg.medConfig)  # noVad
    ep.libInit(cfg)
    tcfg = pj.TransportConfig()
    tcfg.port = 0
    tcfg.tlsConfig.verifyServer = True
    tcfg.tlsConfig.CaListFile = system_ca_bundle()
    transport_id = ep.transportCreate(int(pj.PJSIP_TRANSPORT_TLS), tcfg)
    ep.libStart()
    configure_codecs(pj, ep)
    select_audio_device(pj, ep, null_device=True)
    return ep, transport_id


class EarlyMediaProbe:
    """One-ring early-media experiment. Directors run on pjsua worker threads."""

    def __init__(self, pj: Any, settings: Settings, seconds: int) -> None:
        self._pj = pj
        self._settings = settings
        self._seconds = seconds
        self.account: Any = None
        self._call: Any = None
        self._reg_state: tuple[int, str, bool] | None = None
        self._reg_changed = threading.Event()
        self._ring = threading.Event()
        self._disconnected = False
        self._panel_final: tuple[int, str] | None = None
        self.rtp_seen = 0
        self.rtp_read_ok = False

    # -- directors --------------------------------------------------------

    @contained
    def on_reg_state(self, prm: Any) -> None:
        self._reg_state = (prm.code, prm.reason, prm.code // 100 == 2 and prm.expiration > 0)
        self._reg_changed.set()

    @contained
    def on_incoming(self, call: Any) -> None:
        if self._call is not None:
            self._decline(call)  # experiment consumed; never leave a ring hanging
            return
        info = call.getInfo()
        try:
            door = doorphone_from_uri(info.remoteUri, fallback=self._settings.configured_doorphone())
        except ValueError:
            log.warning("inbound is not a doorphone; declining %d", DECLINE_CODE)
            self._decline(call)
            return
        configured = self._settings.configured_doorphone()
        if configured is not None and not configured.matches_sip_user(door.sip_user):
            log.warning("inbound %s is not the configured panel; declining", door.label)
            self._decline(call)
            return
        self._call = call
        log.info("ring from %s: answering %d with an SDP answer", door.label, PROGRESS_CODE)
        self._answer_progress(call)
        self._ring.set()

    @contained
    def on_call_state(self, call: Any) -> None:
        info = call.getInfo()
        if info.state == self._pj.PJSIP_INV_STATE_DISCONNECTED:
            self._disconnected = True
            self._panel_final = (int(info.lastStatusCode), str(info.lastReason))

    # -- pjsua2 actions ---------------------------------------------------

    def _answer_progress(self, call: Any) -> None:
        prm = self._pj.CallOpParam(True)  # True keeps reqKeyframeMethod and the defaults
        prm.statusCode = PROGRESS_CODE
        prm.opt.audioCount = 1
        prm.opt.videoCount = 1
        prm.opt.textCount = 0  # exactly two m-lines; the panel rejects a third
        try:
            call.answer(prm)
        except self._pj.Error as exc:
            log.error("could not send %d: %s", PROGRESS_CODE, exc.info())

    def _decline(self, call: Any) -> None:
        prm = self._pj.CallOpParam()
        prm.statusCode = DECLINE_CODE  # 486, never 603
        try:
            call.hangup(prm)
        except self._pj.Error as exc:
            log.warning("could not decline %d: %s", DECLINE_CODE, exc.info())

    # -- orchestration (main thread, registered by libCreate) -------------

    def wait_registered(self, budget: float) -> bool:
        if not self._reg_changed.wait(budget) or self._reg_state is None:
            log.error("no REGISTER answer within %.0fs", budget)
            return False
        code, reason, active = self._reg_state
        log.info("REGISTER answered %s %s (active=%s)", code, reason, active)
        return bool(active)

    def wait_for_ring(self, budget: float) -> bool:
        log.info("PRESS THE DOORBELL NOW. Waiting up to %.0fs for one ring.", budget)
        return self._ring.wait(budget)

    def count_rtp(self) -> None:
        # The stack keep-alive (streamKaEnabled via build_acc_config) punches each
        # RTP/RTCP socket with an empty 12-octet RTP packet from the stream's own
        # socket at transport attach; a probe-opened socket would use the wrong port.
        deadline = monotonic() + self._seconds
        while monotonic() < deadline:
            if self._disconnected:
                log.warning("the dialog ended before the window closed")
                break
            self._read_rtp_once()
            sleep(SAMPLE_INTERVAL_S)

    def _read_rtp_once(self) -> None:
        snap = read_media(self._pj, self._call)
        if snap.video_index == NO_STREAM:
            return
        try:  # best effort; the tcpdump capture is the authoritative counter
            stat = self._call.getStreamStat(snap.video_index)
            self.rtp_seen = int(stat.rtcp.rxStat.pkt)
            self.rtp_read_ok = True
            log.info("video RTP received so far (stack stat): %d", self.rtp_seen)
        except Exception:  # noqa: BLE001 - a stat read must never abort the probe
            log.debug("stream stat not readable yet; rely on tcpdump")

    def report(self) -> None:
        log.info("=== early-media observations (record all three) ===")
        counter = f"{self.rtp_seen} (stack stat)" if self.rtp_read_ok else "see tcpdump"
        log.info("1. video RTP before any 200 OK: %s -> early media if > 0", counter)
        log.info("2. handsets still ringing at t+%ds: OPERATOR MUST OBSERVE", self._seconds)
        if self._disconnected:
            code, reason = self._panel_final or (0, "")
            log.info("3. panel ended the dialog: %s %s -> NOT tolerant of a 183+SDP", code, reason)
        else:
            log.info("3. panel neither answered 4xx/5xx nor CANCELled -> tolerant of a 183+SDP")
        log.info("VERIFY the %d carried a two-m-line SDP in the wire dump; do not trust the API.", PROGRESS_CODE)

    def decline_active(self) -> None:
        if self._call is not None and not self._disconnected:
            log.info("declining the call %d Busy here (never 603)", DECLINE_CODE)
            self._decline(self._call)

    def release(self) -> str:
        if self.account is None:
            return "no account was ever created"
        self._reg_changed.clear()
        try:
            self.account.setRegistration(False)
        except self._pj.Error as exc:
            return f"un-REGISTER could not be sent: {exc.info()}"
        if not self._reg_changed.wait(RELEASE_BUDGET_S):
            return "registrar did not answer the un-REGISTER; binding left to expire (up to 900s)"
        _, _, active = self._reg_state or (0, "", False)
        return "released" if not active else "still active after un-REGISTER"


def _make_classes(pj: Any, probe: EarlyMediaProbe) -> tuple[Any, Any]:
    class _ProbeCall(pj.Call):
        @contained
        def onCallState(self, prm: Any) -> None:  # noqa: N802 (pjsua2 API name)
            probe.on_call_state(self)

    class _ProbeAccount(pj.Account):
        @contained
        def onRegState(self, prm: Any) -> None:  # noqa: N802
            probe.on_reg_state(prm)

        @contained
        def onIncomingCall(self, prm: Any) -> None:  # noqa: N802
            probe.on_incoming(_ProbeCall(self, prm.callId))

    return _ProbeAccount, _ProbeCall


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    args = _parse_args(raw)
    refuse_actuators(raw, log)  # the no-actuator rule, checked before anything runs
    if not args.yes_really_ring:
        log.error("refusing: pass --yes-really-ring once a person is at the gate")
        return 2
    settings = load_settings(log)
    if settings is None:
        return 2

    log_file = timestamped_log_file(args.log_dir, "probe_early_media")
    log.info("SIP wire dump (level %d) -> %s", PJSIP_WIRE_LEVEL, log_file)

    creds = provision_credentials(settings)
    pj = load_pjsua2()
    probe = EarlyMediaProbe(pj, settings, args.seconds)
    account_cls, _ = _make_classes(pj, probe)
    ep, transport_id = _bring_up_endpoint(pj, settings, log_file)
    try:
        video = resolve_devices(pj, ep)
        acc_cfg = build_acc_config(pj, creds, settings, transport_id, video)
        probe.account = account_cls()
        probe.account.create(acc_cfg, True)  # registerOnAdd sends REGISTER now
        if not probe.wait_registered(settings.register_timeout_s):
            return 1
        if not probe.wait_for_ring(args.ring_timeout):
            log.error("no ring within the window; nothing to measure")
            return 1
        probe.count_rtp()
        probe.report()
        probe.decline_active()
    finally:
        log.info("release outcome: %s", probe.release())
        if probe.account is not None:
            probe.account.shutdown()  # must run before libDestroy
        ep.libDestroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
