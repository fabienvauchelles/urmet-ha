# Portier dashboard, ring notification and test script

Three optional extras you copy into your own Home Assistant. The integration does
not travel with them: it installs through HACS (see `../docs/install.md`). None of
them opens the door or answers on its own.

## Dashboard, one step

`portier.yaml` is a whole dashboard you paste in one step, no restart and no
`configuration.yaml` edit.

1. Settings > Dashboards > Add dashboard > New dashboard from scratch.
2. Open it, click the pencil to edit, then the three-dot menu > Raw configuration
   editor.
3. Replace what is there with the contents of `portier.yaml`, and save.

The dashboard is a single `custom:urmet-portier-card`. It carries the ring banner,
the live picture and sound, the door and gate openers, the talk button and a
technical panel, and it finds the doorphone through the integration, so it does
not care how your entities are named. If a separate camera points at your door,
set `preview_camera` in the card to show its image while the card is idle.

## Ring notification, optional

`automations.portier.yaml` sends a phone notification on each ring, with a snapshot
from your yard camera and a button that deep-links to the dashboard. Nothing here
answers the panel or opens anything.

- It notifies through `notify.notify`. Replace that with your own target, for
  example `notify.mobile_app_YOUR_PHONE`, or a notify group to reach several phones.
- It snapshots `camera.frontyard`, an example id. Use your own yard camera, never
  the panel: answering the panel to grab a still would stop the ring on the wired
  handsets.
- Its entity ids assume the default doorphone name `Portier` (so
  `event.portier_doorbell` and friends). If you named the device otherwise, adjust
  them to match.

Merge the `- id:` blocks into your `automations.yaml` (it is a list, so append,
do not overwrite), then reload from Developer tools > YAML > Automations, or call
`automation.reload`. No restart.

## Test script, optional

`scripts.portier.yaml` adds `script.portier_test`, which fires the whole
notification chain once so you can check it lands on the phone without waiting for
a real ring. It uses the same `notify.notify` and `camera.frontyard` placeholders,
so set those first. Merge the single `portier_test:` key into your `scripts.yaml`
(it is a dict), reload with `script.reload`, then run the script.
