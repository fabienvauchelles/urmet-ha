# Changelog

Covers the whole project: the add-on gateway, the integration, and the card.

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
