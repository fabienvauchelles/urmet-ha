# Hardware results

Filled by WP13, one section per session. Copy the template below for each session
and fill it in. Every line of the test plan (`hardware-test-plan.md`, items 1 to
12) must end with an entry here saying what happened or why it was not run. Never
leave an item blank: "not run, out of daylight" is a result.

Record raw numbers, not conclusions. Two attempts are not a rate.

---

## Session template (copy for each run)

### Session YYYY-MM-DD, <operator>

- Add-on / gateway commit: `<sha>`
- pjproject / pjsua2 version: `<version>`
- Doorphone MAC: `<mac>`
- Conditions: daylight yes/no, household warned yes/no, second person at gate yes/no
- tcpdump capture file: `<path>`
- SIP wire dump file: `<path>`

| # | Item | Run? | Result / raw numbers | Verdict or next step |
|---|---|---|---|---|
| 1 | MediaTap boundary end to end | | frames, bytes, stalls: | |
| 2 | Early media, one ring | | RTP before 200: ; handsets at t+20s: ; panel 4xx/5xx or CANCEL: | early media yes/no |
| 3 | Two-way audio to loudspeaker | | audible out: ; audible back: ; echo: | |
| 4 | Keyframe request honoured | | time to first frame with/without request: ; method on wire: | PLI / FIR / neither |
| 5 | Answered-ring pipeline 656x656 | | CPU: ; watchdog fired: ; picture held: | |
| 6 | 408 stall rate | | attempts: ; stalls: ; final codes: | |
| 7 | 486 vs 603 on the branch | | handsets under 486: ; under 603: | |
| 8 | TLS binding survival 48 h | | refresh cadence: ; stale events: ; NAT rebind: | is 300 s liveness enough? |
| 9 | Ghost bindings after unclean stop | | after kill: ; after power cut: ; after OS update: | |
| 10 | Open acknowledgement latency `[ACTUATION]` | | latency to 200: ; Signal count in log: ; physical result: | |
| 11 | Another device already in a call | | panel behaviour: ; gateway saw: | |
| 12 | Notification chain on the test phone | | picture: ; actions: ; deep link: ; channel: ; freshness guard: | |

Notes and anything unexpected:

-

---

<!-- Add the next session below this line, copying the template above. -->
