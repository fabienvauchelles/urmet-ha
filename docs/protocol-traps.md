# Protocol traps: read this first

Every item here was measured, hit, patched or refused on the real installation
(Mini Note 1722/958, 2Voice, Avidsen Slidymoove 600 gate). Each one is expensive
to rediscover. Ordered by how much it costs to relearn. Sources are the recon
reports and the `urmet-sdk` specs.

## The ten that stop calls or damage things

1. **User-Agent is load bearing.** Send
   `UrmetCallForwarding-Android/4.5.4-02 (belle-sip/1.6.3)` or the panel answers
   `486 Busy here` to every INVITE while perfectly idle, with every other header
   already correct. The 486 is a lie about being busy. It is the first thing to
   re-check when calls start failing after a firmware or vendor-app update. Pinned
   in `pjsip_stack.py`.

2. **Never configure an outbound proxy and never emit your own `Route`.** One does,
   every out-of-dialog INVITE dies with a bare `503` about 30 ms after the
   authenticated retry, while registration stays perfectly green. Diagnostic that
   cracked it: an INVITE to a MAC that cannot exist returns the same 503, so the
   router module never ran. Inside a dialog the rule inverts: derive the route set
   per dialog from `Record-Route`, in the order received on a ring accepted,
   reversed on a call placed.

3. **An answered ring has a black picture without the stream keep-alive.** The
   panel offers video `a=sendonly`, so our answer is `recvonly` and encodes
   nothing; the relay only sends where it has already seen a packet come from. The
   fix is `PJMEDIA_STREAM_ENABLE_KA` in the build plus `streamKaEnabled = True` on
   the account: a 12-octet empty RTP packet leaves the stream's own socket at
   attach. Measured: 0 video packets without it, 535 with it. A separate socket
   punches the wrong source port and does nothing.

4. **Never auto-retry an actuator.** The Slidymoove 600 is step by step: each
   `Signal=2` advances open, stop, close, and the panel acknowledges all three
   byte for byte identically. A retry after an unacknowledged first command is a
   reversal that leaves the leaf stopped half open. Every non-200 and every
   timeout is UNKNOWN, never failed and never open. Two commands must never be in
   flight in one dialog at once.

5. **Force `null_sound_device` on anything unattended.** Left to itself the SDK
   opens a real ALSA device and wires it into every call, so a call placed from a
   gateway puts the room around the machine onto the street panel. Measured
   outgoing level 0.42 with nobody speaking.

6. **Release the binding, and report a release you could not confirm.** `stop()`
   used to claim a release it never obtained, and the binding then sat at the
   registrar for its full 900 s expiry. Wait for the un-REGISTER final response,
   retry a busy `regc` for 2 s at 50 ms, and surface an unconfirmed release. A
   leaked binding is a doorbell outage for up to 900 s.

7. **Drop every native `Call` before `libDestroy`, join the call thread first.** A
   pjsua2 `Call` still referenced when the library is destroyed aborts the
   process on an assertion. `gc.collect()` before destroy, and never keep a
   reference to a native call across a teardown.

8. **Publish the ring from the inbound INVITE.** pjsua sets the invite session to
   INCOMING before it binds the dialog to a call object, so no RINGING state ever
   reaches a callback. Alert from the INVITE itself, before the 180. Discriminate
   a doorbell on the `From` user part only (underscore MAC form): the ring carries
   no `mac:` header, no subject, no body marker.

9. **Decline an unclaimed INVITE with 486, never 603.** RFC 3261 16.7 has a
   conforming proxy cancel every branch on a 6xx, which would silence the
   household handsets. 486 leaves them ringing. This is unprobed on this proxy, so
   603 is only ever tested with the household warned.

10. **Set `noVad = True`, and mute by transmitting silence.** With VAD on, a quiet
    doorway put 35 RTP packets on the wire in 29 s where 20 ms PCMA should put
    about 1450, and the syllable a silence gate eats is the first one. Ceasing to
    transmit also stops feeding the relay's source-address rule.

## Build and binding traps

- Build pjproject with the wildcard-certificate patch (`sip.urmet.com` presents
  `*.urmet.com`, which RFC 5922 forbids and stock PJSIP refuses),
  `PJMEDIA_HAS_SRTP`, `PJMEDIA_HAS_VIDEO`, `PJSIP_MAX_PKT_LEN 8000` (video SDP and
  Flexisip REGISTER responses exceed the 4000 default), `PJ_LOG_MAX_LEVEL 5` (6
  floods stdout and is the initial runtime level too), and
  `PJMEDIA_STREAM_ENABLE_KA 1`.
- `make dep` produces corrupt `.depend` files, so it is skipped; a `config_site.h`
  change then needs `make clean` or it recompiles nothing.
- Never `pip install pjsua2` (an unrelated stale project). Never `make install`
  inside `pjsip-apps/src/swig/python`: it writes outside the venv and still exits
  0. Use `make wheel` plus `pip install --force-reinstall`, and delete `build/`.
- `setVideoCodecParam` aborts the process once `decFmtp` is set. Do not pin H.264
  format parameters that way. This crash trap was almost lost in the repo split.
- A misspelled pjsua2 attribute is accepted in silence (SWIG proxies allow new
  attributes), so `caListFile` sets a stray field while `CaListFile` stays empty
  and TLS fails with no CA error in the log.
- The registrar keeps several bindings per AOR and evicts none, so registering
  here does not knock the phones offline. The old "one registration per AOR, mint
  a dedicated account" belief was refuted; `dedicated_account` stays false.

## Media reality

- There is no still-image API. A frame exists only inside a live SIP dialog:
  no snapshot, no RTSP, no state query. A `camera` entity would place a SIP call
  per thumbnail, which the specs call a denial of service on the doorbell.
- Answered-ring geometry is 656x656; on-demand is 320x240 settling after ~3 s.
  Read geometry from the decoded stream, never from the renderer.
- Arm the video tap on a cadence, not once: a call reaching its media state does
  not yet carry a decodable picture. Stop only on `NoVideoOfferedError`, which is
  terminal; a plain `CallError` means "not up yet, ask again".
- The panel identity is proxy-asserted, not authenticated: anything that can place
  a call with the right `From` user part is a doorbell as far as we can tell. Never
  automate an open on the strength of a ring alone.
