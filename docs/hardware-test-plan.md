# Hardware test plan

Everything here can only be settled against the real panel. Each item is a known
unknown, not a formality, and maps one to one onto DESIGN section 10.5. Record
each run in `hardware-results.md`, one section per session.

## Safety rules, non-negotiable

- **Every `[ACTUATION]` step is run attended, in daylight, with someone who can
  see the gate.** An open gate is an unattended entrance and there is no way to
  confirm it closed again. Every physical open needs an explicit go, each time. No
  autonomous session may send `Signal=1` or `Signal=2`.
- **Never auto-retry an actuator.** On this step-by-step gate a second pulse is a
  reversal. After any actuator step, grep the run log for `Signal=` and confirm
  exactly one went out.
- **The 603 test (item 7) disturbs the household.** Warn everyone first, and run it
  only with the handsets watched. Default to 486 everywhere else.
- The probes force `null_sound_device`, never actuate, and refuse an actuator
  argument. `probe_early_media.py` also refuses to run without `--yes-really-ring`.

## 1. The MediaTap boundary end to end

The SDK states this surface has never run against the panel: the audio tap and the
video recorder on a live call are unproven, and the gateway depends on exactly it.
Procedure: place one on-demand `view_door` call (a view, not an open), arm the
audio tap and the video pipeline, and read the doubled counters at both ends.
Record: frames and bytes through the tap, whether the recorder writes, any stall.
Not actuation.

## 2. Early media, one ring `[probe]`

Settles whether the visitor can be seen or heard without sending 200 OK. Run
`python tools/probe_early_media.py --yes-really-ring` with a `tcpdump -i any udp`
capture alongside, and a person at the gate. Full procedure, one ring:

1. The probe writes the full SIP dump at PJ_LOG_LEVEL 5 to a file. tcpdump gives
   the authoritative RTP counters (SIP over TLS is encrypted).
2. It registers with the stored account, pinned User-Agent, wildcard-realm
   credential, TLS 5061, no Route, exactly as the SDK does.
3. On the INVITE from the doorphone MAC it answers `183 Session Progress` with the
   SDP answer instead of 180. Read off the wire dump whether the 183 actually
   carried a two-m-line SDP; never trust the API for it.
4. The stream keep-alive punches each RTP and RTCP socket at attach.
5. It counts received video RTP for 20 s and NEVER sends 200 OK.
6. A human watches the household handsets and the Urmet app for the whole 20 s.
7. It declines with 486 Busy here (never 603) and releases the binding.

Record all three observations: video RTP before any 200 OK (early media if > 0);
handsets still ringing at t+20 s (non-destructive if yes); the panel neither
answered 4xx/5xx nor CANCELled (tolerant of a 183+SDP if so). Any one no confirms
the DESIGN verdict and the probe is deleted after the result is written here.

## 3. Two-way audio to the panel loudspeaker

Every measurement so far was taken at night with a silent doorway, so only that
packets leave is established, not that the panel plays them. Procedure: answer a
ring or place a view call and speak, with a second person at the gate confirming
they hear it, and confirm the reverse. Record: audible both ways, level readings,
any echo. Not actuation.

## 4. Which keyframe request the panel honours

The panel advertises `nack pli` and `ccm fir`; which it honours was never
isolated, and it decides whether the ~9 s intra interval (latency term B7) is
reachable at all. Procedure: on an answered ring, answer with `CallOpParam(True)`
so the keyframe request is not zeroed, and time to first decodable frame; compare
against a run where no request is sent. Record: time to first frame each way, and
which method the wire dump shows. Not actuation.

## 5. The answered-ring pipeline at 656x656

Eight times the bandwidth of an on-demand view, and its CPU cost was never measured
on any hardware. Procedure: answer a ring, run the full video pipeline, and watch
CPU and the two watchdog budgets (`SILENCE_TIMEOUT_S`, `STARTUP_TIMEOUT_S`).
Record: CPU over the call, whether the watchdog fired, whether the picture held.
Not actuation.

## 6. The 408 stall rate

One of two observed answered rings bridged its audio, moved towards confirmation,
stopped there and ended with 408 about a minute later. Two attempts are not a
rate. Procedure: answer many rings over the sessions and count how many fail to
reach media within the 15 s budget. Record: attempts, stalls, and the final code
each time. Not actuation.

## 7. 486 leaves handsets ringing, 603 cancels them `[disruptive]`

Objective (d) is never to disturb the handsets. Procedure: with the household
warned and the handsets watched, let the probe decline a ring 486 and confirm the
handsets keep ringing; then, only once and only with everyone warned, test a 603
and confirm whether it cancels every branch. Record: handset behaviour under each.
Default stays 486 forever.

## 8. TLS binding survival over days `[probe]`

`keepalive_interval_s` does not reach a TLS transport, no `Flow-Timer` was ever
observed, and the registration flag is the stack's last answer, not a probe.
Procedure: run `python tools/probe_keepalive.py --hours 48 > run.log 2>&1` and
leave it. It logs every REGISTER outcome, its own refreshes included, and a
liveness sample each minute. Record: the natural refresh cadence, any binding that
went stale, and whether ISP NAT rebinding dropped it. This one may run unattended.

## 9. Ghost bindings after an unclean stop

A binding left behind sits at the registrar for its full 900 s and takes its share
of the fork. Procedure: kill the add-on uncleanly, then power-cut the box, then
take an HA OS update, and after each check whether a stale binding remains.
Record: bindings present after each event, and whether the SIGTERM release path
cleared them. Not actuation.

## 10. Open acknowledgement latency `[ACTUATION]`

Never measured anywhere in the corpus; the test plans only ever asserted "receipt
within five seconds". Procedure, attended and in daylight, with the gate watched:
send exactly one open and time the panel's 200 OK. Confirm exactly one `Signal=`
in the log. Record: latency to the acknowledgement, and the physical result seen.

## 11. Panel behaviour when another device is already in a call

Unknown. Procedure: put a household handset or the Urmet app in a call with the
panel, then place a view call from the gateway and observe. Record: what the panel
does, and what the gateway sees. Not actuation.

## 12. The notification chain on the test phone

The whole chain on the test phone, including the channel settings Android freezes
at creation. Procedure: run `script.portier_test`, then a real ring, and check the
picture, both actions, the deep link, and the channel behaviour. Record: what
arrived, latency, and whether the freshness guard on the open action held.
