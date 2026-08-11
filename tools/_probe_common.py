"""Shared plumbing for the hand-run hardware probes in this directory.

Neither probe is part of the test suite; both import the SDK and pjsua2 and are
run by a maintainer against the live installation (see docs/hardware-test-plan.md).
This module holds what they share and nothing a probe owns alone: loading
settings, provisioning SIP credentials from the cloud, the actuator refusal that
neither probe is ever allowed past, a timestamped log file, and the system CA
bundle the TLS transport verifies against.

A probe imports this as a sibling module (``from _probe_common import ...``),
which works because a directly-run script puts its own directory on the path.
Run the probes as ``python tools/<probe>.py``.
"""

from __future__ import annotations

import datetime
import logging
import ssl
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from urmet_sdk import CloudClient, Settings, UrmetClient

# argv tokens that would imply actuation. Neither probe has a code path that sends
# Signal=1 or Signal=2; the presence of any of these aborts the run anyway, so a
# fat-fingered actuator argument can never reach a device wired to a building.
FORBIDDEN_TOKENS = ("open", "door", "gate", "signal", "actuator", "unlock", "info")


def configure_logging(name: str) -> logging.Logger:
    """Set up stdout logging for a probe and return its logger."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return logging.getLogger(name)


def refuse_actuators(argv: list[str], log: logging.Logger) -> None:
    """Abort if anything on argv looks like an actuator command.

    Defence in depth: the probes never actuate, and this refuses an actuator
    argument on top of that, before any stack is brought up.
    """
    hits = sorted({token.lower().lstrip("-") for token in argv} & set(FORBIDDEN_TOKENS))
    if hits:
        log.error("refusing: these probes never actuate; unexpected token(s) %s", hits)
        raise SystemExit(2)


def load_settings(log: logging.Logger) -> Settings | None:
    """Read ``URMET_*`` settings, forcing the null sound device.

    ``null_sound_device`` is forced true so a probe can never open the microphone
    of the machine it runs on (DESIGN section 5.8 trap 4). Returns None and logs
    the offending option names (never their values) when the configuration is
    incomplete.
    """
    try:
        return Settings(null_sound_device=True)
    except ValidationError as exc:
        log.error("configuration invalid; check options %s", [e["loc"] for e in exc.errors()])
        return None


def provision_credentials(settings: Settings) -> Any:
    """Log in to the cloud and return the stored SIP credentials.

    Uses the SDK's own cloud plane, so the probe registers with exactly the
    account the installation is bound to. No dedicated account is ever minted.
    """
    cloud = CloudClient(settings.cloud_base_url, timeout_s=settings.http_timeout_s)
    client = UrmetClient(settings, cloud=cloud)  # transport=None: cloud plane only
    client.login()
    return client.provision()


def timestamped_log_file(log_dir: Path, stem: str) -> Path:
    """Return ``<log_dir>/<stem>_YYYYMMDD_HHMMSS.log``, creating the directory."""
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return log_dir / f"{stem}_{stamp}.log"


def system_ca_bundle() -> str:
    """The system CA bundle path, or exit when there is none to verify against."""
    paths = ssl.get_default_verify_paths()
    bundle = paths.cafile or paths.openssl_cafile
    if not bundle or not Path(bundle).is_file():
        raise SystemExit("no system CA bundle found; install ca-certificates")
    return bundle
