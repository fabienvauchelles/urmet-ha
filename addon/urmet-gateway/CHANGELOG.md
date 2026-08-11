# Changelog

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
