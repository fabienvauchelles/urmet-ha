# Changelog

Covers the whole project: the add-on gateway, the integration, and the card.

## 0.2.2

- The integration carries its own brand images in `custom_components/urmet/brand/`,
  so Home Assistant shows the Urmet mark instead of the placeholder puzzle piece on
  the integrations page, in the device registry and in HACS. Home Assistant 2026.3
  and later reads that directory and prefers it over the brands CDN, which spares a
  pull request to `home-assistant/brands` and its review delay. Eight files: `icon`
  and `logo`, each in a normal and an hDPI size, each with a `dark_` variant so the
  mark stays readable on both themes.

## 0.2.1

- The add-on image now ships the ingress diagnostics page. Its static files
  (`diag/index.html`, `diag/diag.js`) are declared as package data, so they
  travel inside the wheel instead of being left behind by the build, which is
  why the gateway used to log "no diagnostics page".
- Biome lints and formats the card; `make card` now runs it.

## 0.2.0

Refactor onto the urmet-sdk 0.2 contract, and cross-repo coherence. No behavior
change on the deployed box.

- The gateway builds on urmet-sdk 0.2: `director_failures` and
  `doorphone_from_uri` come from the package root, and
  `CallState.is_streaming` / `.is_terminal` replace the gateway-owned state sets.
- The scattered gateway error types are consolidated under `GatewayError`, and
  the runtime composition root moved to `runtime.py`. Integration per-entry state
  moved onto `entry.runtime_data`, services register once per instance, and a
  service resolves its target entry (raising on ambiguity) instead of always
  taking the first one.
- Dead options removed (`look_timeout_s`, the `show_tech` HA toggle). The version
  is single-sourced, and the stale submodule CI is gone. The three wire mirrors
  (gateway, integration, card) carry the same audio-stats fields.
- Requires urmet-sdk 0.2.0.

## 0.1.5

- You can hear the visitor: the video panel no longer stays muted, and the talk
  microphone cancels echo, noise and gain drift, so the visitor no longer hears
  themselves once the panel audio plays out loud on the phone.
- The doorphone rings, the card shows the visitor, and you tap Décrocher to take
  the call. The card never answers or joins a call on its own, so it can't latch
  onto a stale streaming leg; it negotiates only on an explicit Décrocher or
  Regarder, one link at a time.
- The gateway hangs a monitor call up once its last browser leg closes, after a
  short grace for page reloads. A stale streaming call used to linger and swallow
  the next offer, leaving the picture blank until a watchdog tore it down.
- The card height follows its content, removing the empty band that sat below the
  button on a phone.

## 0.1.3

- One open action: the gateway opens inside the live call when one is streaming
  and places a short call otherwise, so the caller no longer picks a dialog. The
  `call_id` parameter is gone from the open endpoints.

## 0.1.2

- The card shows a neutral placeholder when idle instead of a camera by default,
  the gate button reads "Portail", and no shipped example references a specific
  camera. No gateway change.

## 0.1.1

- The add-on announces itself to the Supervisor, so the Portier Urmet integration
  sets itself up with no host or port to type.
- Dropped the AppArmor profile that never loaded; the add-on runs without a custom
  profile for now.

## 0.1.0

First release.

- Two-stage image: PJSIP 2.17 built from a sha256-pinned source tarball with the
  vendored wildcard-certificate patch and the required `config_site.h` switches
  (SRTP mandatory, video, TLS, 8000-byte packets, log level 5, stream
  keepalive), then a slim runtime with ffmpeg and the pjsua2 wheel.
- s6-overlay v3 service tree: `init-urmet` exports the add-on options as the
  gateway environment, `urmet-gateway` runs the gateway in the foreground so
  SIGTERM reaches it, and the finish script reports the SIP release outcome.
- Registers with the Urmet cloud, reports rings, answers on request, taps audio
  and video, and opens the door or steps the gate.
- Diagnostics page on ingress; media leg on the host network for LAN WebRTC.
- amd64 only.
