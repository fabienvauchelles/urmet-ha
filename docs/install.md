# Install

Three pieces, installed in this order: the add-on (the SIP gateway), the
integration (through HACS), then the dashboard and automations. Do not reorder:
the integration needs the add-on answering, and the dashboard needs the
integration's entities.

## 1. The add-on

1. Settings > Apps > Add-on store > top-right menu > Repositories. Add
   `https://github.com/fabienvauchelles/urmet-ha` and reload the store.
2. Install **Urmet doorphone gateway**. The pre-built `amd64` image is pulled
   from `ghcr.io/fabienvauchelles/urmet-gateway`, so there is no local build.
3. Configure the options: `email` and `password` (the Urmet cloud account),
   `doorphone_mac`, `doorphone_name`. Leave `look_timeout_s` and `log_level` at
   their defaults.
4. Start the add-on. `boot: auto` keeps it started across reboots.
5. Open the add-on's ingress panel and confirm `GET /api/health` answers
   `{"ok": true}`. The port opens before SIP registration, so health answers
   within about 2 s even while the binding is still coming up.

## 2. The integration (HACS)

The integration is not on the default add-on store. It installs through HACS as a
custom repository.

1. HACS > top-right menu > Custom repositories. Add
   `https://github.com/fabienvauchelles/urmet-ha`, category **Integration**.
2. Download **Portier Urmet**.
3. **Restart Home Assistant Core** (Developer tools > YAML > Restart, or Settings
   > System > Restart). A new integration is not loaded by a config reload.
4. Settings > Devices & Services > Add integration > **Portier Urmet**.
5. Host `172.30.32.1` (the Supervisor bridge gateway, how a Core container
   reaches a `host_network` add-on), port `8099`. The flow reads the doorphone
   MAC from the gateway and uses it as the unique id. If it aborts with
   `no_doorphone`, set `doorphone_mac` in the add-on options and retry.

## 3. The dashboard and automations

The example dashboard, automations and test script live in `dashboard/`. Full
landing paths, the merge rules, the `lovelace:` block and the single core restart
it needs are in `../dashboard/README.md`. In short: copy `dashboard/portier.yaml`
into your config's `dashboards/` folder, merge `automations.portier.yaml` and
`scripts.portier.yaml` into your existing `automations.yaml` and `scripts.yaml`,
add the `lovelace:` block to `configuration.yaml`, and restart core once for the
`lovelace:` block. Then run `script.portier_test` to put the whole notification
chain on the phone.

## Two-way audio needs a secure context

Listening and watching work anywhere. Talking back does not: the microphone needs
a browser secure context, and a plain `http://` tab on the LAN (for example
`http://homeassistant.local`) is not one. Browsers only expose `getUserMedia` on
`https://` origins and on `http://localhost`, so a LAN hostname over plain HTTP is
refused. The card disables the talk control with a plain sentence rather than
failing silently.

For two-way audio use one of:

- the Home Assistant **companion app** (iOS or Android), which grants the
  microphone natively, or
- your own HTTPS origin for Home Assistant, for example
  `https://home-assistant.example.com`. Use whatever HTTPS URL your instance is
  reachable at (a reverse proxy, Nabu Casa, or a self-signed cert all qualify).

Not `http` on the LAN. This is a browser rule, not a limitation of the gateway.
