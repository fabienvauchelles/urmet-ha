"""Runtime configuration for the gateway, beside the SDK's own settings.

Prefix ``URMET_GW_``, read from the same ``.env`` the SDK's ``URMET_`` settings
are read from, so one file configures the doorphone and the gateway in front of
it. Nothing here overlaps ``urmet_sdk.Settings``: the two are built side by side
and neither reads the other's variables.

There is deliberately no ``null_sound_device`` field. The composition root forces
that flag on as a literal, so no deployment can open the server's own microphone
onto the street panel by editing a variable. See ``main.force_null_sound_device``.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from urmet_gateway.constants import SERVER_PORT


class GatewaySettings(BaseSettings):
    """Where the gateway binds, how loud it logs, and two media budgets.

    Populated from environment variables prefixed ``URMET_GW_`` (or a local
    ``.env``), e.g. ``URMET_GW_PORT``, ``URMET_GW_LOG_LEVEL``. The credentials
    and the doorphone identity are the SDK's ``URMET_`` settings, not these.
    """

    model_config = SettingsConfigDict(
        env_prefix="URMET_GW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # The host network the add-on runs on, so the browser reaches the media leg
    # over ICE host candidates on the LAN (DESIGN 2.3, 5.9). The HTTP and event
    # surface is reached through ingress, which authenticates in front of it, so
    # the gateway itself authenticates nobody.
    host: str = "0.0.0.0"
    port: int = SERVER_PORT

    # One of debug, info, warning, error (config.yaml schema).
    log_level: str = "info"

    # How long a session holds its first look for a picture off. Zero, because
    # the panel's ~9 s to a first frame is its own keyframe cadence, not a settle
    # a client can wait its way out of (DESIGN 3.3, urmet-web trap 11).
    video_settle_s: float = 0.0
