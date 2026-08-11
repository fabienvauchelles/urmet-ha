#!/usr/bin/env python3
"""Find out whether the TLS SIP binding survives long idle, and whether the 300 s
liveness REGISTER is enough (DESIGN section 10.5 item 8, section 12 risk 7).

Registers exactly as the SDK does and stays registered for many hours, logging
every REGISTER outcome pjsua reports (its own ~900 s refreshes included) and a
periodic liveness sample, so a maintainer can find the real keepalive number and
whether ISP NAT rebinding ever drops the binding. It may run unattended.

Non-destructive by construction: it never places a call and never actuates. An
incidental ring is left to the household, alerted 180 Ringing only, never answered
and never declined 603 (which would cancel the household branches).

Guards: refuses any actuator command (no actuator code path exists); prints the
release outcome so a leaked binding is visible. ``--yes-really-ring`` is not
required, because the probe never rings anyone.
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from datetime import datetime, timezone
from time import monotonic
from typing import Any

from _probe_common import (
    configure_logging,
    load_settings,
    provision_credentials,
    refuse_actuators,
)

from urmet_sdk import PjsipTransport
from urmet_sdk.domain.models import RegistrationState
from urmet_sdk.errors import UrmetError
from urmet_sdk.sip.protocol import CallHandle

log = configure_logging("probe_keepalive")

DEFAULT_HOURS = 48.0
DEFAULT_SAMPLE_S = 60.0
# No successful REGISTER for this long means the binding is dead even if the stack
# still claims otherwise: DESIGN section 5.6 reports registered=false past 2 x the
# 300 s liveness cadence.
STALE_AFTER_S = 600.0


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class KeepaliveProbe:
    """Counts REGISTER outcomes and remembers when the binding was last active."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.outcomes = 0
        self._last_active_at: float | None = None

    def on_registration(self, state: RegistrationState) -> None:
        """Log every REGISTER outcome the transport reports, refreshes included."""
        now = monotonic()
        with self._lock:
            self.outcomes += 1
            if state.active:
                self._last_active_at = now
            count = self.outcomes
        log.info(
            "%s REGISTER outcome #%d: active=%s code=%d %s",
            _utc(), count, state.active, state.status_code, state.reason,
        )

    def on_incoming(self, call: CallHandle, from_uri: str) -> bool:
        """Claim an incidental ring so the SDK alerts 180 and never declines 603.

        Returning False would make the SDK hang up with code 0, which pjsua sends
        as 603 Decline, and a conforming proxy cancels every household branch on a
        6xx. Claiming sends 180 Ringing instead; the probe never answers, and the
        panel CANCELs the branch after about 30 s. The household is undisturbed.
        """
        log.info("%s incidental ring from %s left to the household (180 only)", _utc(), from_uri)
        return True

    def seconds_since_active(self) -> float | None:
        with self._lock:
            if self._last_active_at is None:
                return None
            return monotonic() - self._last_active_at


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="probe_keepalive",
        description="Keep a SIP binding registered for hours and log every refresh.",
    )
    parser.add_argument("--hours", type=float, default=DEFAULT_HOURS, help="how long to stay up")
    parser.add_argument("--sample", type=float, default=DEFAULT_SAMPLE_S, help="liveness cadence")
    return parser.parse_args(argv)


def _sample(probe: KeepaliveProbe) -> None:
    idle = probe.seconds_since_active()
    if idle is None:
        log.warning("%s liveness: no active binding yet", _utc())
    elif idle > STALE_AFTER_S:
        log.error("%s liveness: no successful REGISTER for %.0fs; binding presumed DEAD", _utc(), idle)
    else:
        log.info("%s liveness: last REGISTER %.0fs ago (%d outcomes)", _utc(), idle, probe.outcomes)


def _release(transport: Any) -> None:
    try:
        transport.attach_thread()
        transport.unregister()
        outcome = "released (registrar confirmed)"
    except UrmetError as exc:
        outcome = f"NOT released: {exc}; binding left to expire (up to 900s)"
    log.info("release outcome: %s", outcome)
    transport.shutdown()


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    args = _parse_args(raw)
    refuse_actuators(raw, log)  # the no-actuator rule, checked before anything runs
    settings = load_settings(log)
    if settings is None:
        return 2

    # For a 48 h unattended run, redirect stdout to a file: the pjsip and refresh
    # lines all go to the console, e.g. python tools/probe_keepalive.py > run.log 2>&1
    log.info("keepalive: staying up %.1f h, sampling every %.0fs", args.hours, args.sample)

    creds = provision_credentials(settings)
    probe = KeepaliveProbe()
    transport = PjsipTransport(settings)
    transport.on_registration(probe.on_registration)
    transport.on_incoming(probe.on_incoming)

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    transport.attach_thread()
    transport.register(creds)
    deadline = monotonic() + args.hours * 3600.0
    try:
        while not stop.is_set() and monotonic() < deadline:
            if stop.wait(args.sample):
                break
            _sample(probe)
    finally:
        _release(transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
