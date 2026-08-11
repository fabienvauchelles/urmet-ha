import type { ReactiveController, ReactiveControllerHost } from "lit";
import {
  DEFAULT_AUTO_START,
  deriveViewModel,
  resolveEntry,
  type CardViewModel,
  type HomeAssistant,
  type LinkState,
  type StateWire,
  type UnsubscribeFunc,
  type UrmetCardConfig,
} from "./state";
import * as gw from "./link/hass";
import { browserDeps, UnsupportedCodecError, WebrtcLink } from "./link/webrtc";

// The link use case: subscription, the answer/look/negotiate/teardown state
// machine, the mic path, the ring counter. It lives outside the element so the
// card class stays a view: the controller drives host.requestUpdate whenever a
// pushed gateway event or a WebRTC transition changes what must be drawn.
export class LinkController implements ReactiveController {
  hass?: HomeAssistant;
  config?: UrmetCardConfig;

  vm: CardViewModel = deriveViewModel(undefined);
  linkState: LinkState = "idle";
  error?: string;
  resolveError?: string;
  talking = false;
  hasRemote = false;
  ringSeconds = 0;
  stream?: MediaStream;
  sessionId?: string;
  ignoredCallId?: string;
  connecting = false;

  private entryId?: string;
  private state?: StateWire;
  private unsub?: UnsubscribeFunc;
  private subscribing = false;
  private link?: WebrtcLink;
  private pendingCallId: string | null = null;
  private autoStarted = false;
  // Armed until the first state after the card mounts: a ring already in progress
  // when we arrive (a notification tap) is answered on sight; a ring that starts
  // while the card is already open only shows the banner.
  private answerArmed = true;
  private ringTimer?: ReturnType<typeof setInterval>;
  private ringStart?: number;

  constructor(private readonly host: ReactiveControllerHost) {
    host.addController(this);
  }

  get hasLink(): boolean {
    return !!this.link;
  }

  hostConnected(): void {
    this.ensureStarted();
  }

  hostDisconnected(): void {
    this.teardown();
    if (this.unsub) {
      void this.unsub().catch((error) => console.debug("urmet: unsubscribe failed", error));
      this.unsub = undefined;
    }
    this.stopRingTimer();
  }

  updateHass(hass: HomeAssistant): void {
    this.hass = hass;
    this.ensureStarted();
  }

  ensureStarted(): void {
    const host = this.host as unknown as { isConnected: boolean };
    if (!host.isConnected || this.unsub || this.subscribing || !this.hass) return;
    // Re-resolve on every push while unsubscribed so a late registry heals.
    const resolved = resolveEntry(this.config ?? { type: "" }, this.hass);
    this.resolveError = undefined;
    if ("pending" in resolved) return;
    if ("error" in resolved) {
      this.resolveError = resolved.error;
      return;
    }
    this.entryId = resolved.entryId;
    this.subscribing = true;
    const hass = this.hass;
    void gw
      .subscribeState(hass, this.entryId, (state) => this.onState(state))
      .then((unsub) => {
        this.unsub = unsub;
      })
      .catch((error) => {
        this.error = "Impossible de se connecter à la passerelle du portier.";
        console.warn("urmet: subscribe failed", error);
        this.host.requestUpdate();
      })
      .finally(() => {
        this.subscribing = false;
      });
  }

  answer(callId: string): void {
    const hass = this.hass;
    if (!hass) return;
    this.error = undefined;
    this.ignoredCallId = undefined;
    this.linkState = "answering";
    this.pendingCallId = callId;
    this.host.requestUpdate();
    void gw.answerCall(hass, callId).catch((error) => this.fail("Impossible de répondre à l'appel.", error));
  }

  look(): void {
    const hass = this.hass;
    if (!hass) return;
    this.error = undefined;
    this.linkState = "answering";
    this.pendingCallId = null;
    this.host.requestUpdate();
    void gw.look(hass).catch((error) => this.fail("Impossible de regarder le portier.", error));
  }

  ignore(callId: string): void {
    this.ignoredCallId = callId;
    this.stopRingTimer();
    this.host.requestUpdate();
  }

  hangUp(): void {
    const hass = this.hass;
    const callId = this.vm.activeCall?.id;
    this.teardown();
    this.host.requestUpdate();
    if (hass) void gw.hangUp(hass, callId).catch((error) => console.warn("urmet: hang up failed", error));
  }

  async toggleTalk(): Promise<void> {
    const hass = this.hass;
    const link = this.link;
    if (!hass || !link) return;
    try {
      if (!this.talking) {
        await link.enableMic();
        link.setMicEnabled(true);
        await gw.setMic(hass, false);
        this.talking = true;
      } else {
        link.setMicEnabled(false);
        await gw.setMic(hass, true);
        this.talking = false;
      }
    } catch (error) {
      this.error = "Le micro n'a pas pu être activé.";
      console.warn("urmet: mic toggle failed", error);
    }
    this.host.requestUpdate();
  }

  teardown(): void {
    const hass = this.hass;
    const entryId = this.entryId;
    const sessionId = this.sessionId;
    this.link?.close();
    this.link = undefined;
    this.stream = undefined;
    this.hasRemote = false;
    this.sessionId = undefined;
    this.pendingCallId = null;
    this.connecting = false;
    this.talking = false;
    this.linkState = "idle";
    if (hass && entryId && sessionId) {
      void gw
        .closeSession(hass, entryId, sessionId)
        .catch((error) => console.debug("urmet: close session failed", error));
    }
  }

  private onState(state: StateWire): void {
    this.state = state;
    this.vm = deriveViewModel(state);
    this.react();
  }

  private react(): void {
    const vm = this.vm;
    const mode = this.config?.auto_start ?? DEFAULT_AUTO_START;
    if (vm.ringingCall && vm.ringingCall.id !== this.ignoredCallId) this.ensureRingTimer();
    else this.stopRingTimer();

    this.advancePending();

    if (this.linkState === "idle") {
      const ring = vm.ringingCall;
      if (vm.streamingCall && mode !== "never") void this.negotiate(null);
      else if (this.answerArmed && mode === "on_ring" && ring && ring.id !== this.ignoredCallId) {
        this.answer(ring.id);
      } else if (mode === "always" && !vm.activeCall && !this.autoStarted) {
        this.autoStarted = true;
        this.look();
      }
    } else if (this.linkState === "live" && vm.degraded) {
      this.linkState = "degraded";
    }
    // The arrival window is one state wide: only a ring present when the card
    // first draws auto-answers, never one that arrives afterwards.
    this.answerArmed = false;
    this.host.requestUpdate();
  }

  private advancePending(): void {
    if (this.linkState !== "answering") return;
    const calls = this.state?.calls ?? [];
    const pending = this.pendingCallId ? calls.find((c) => c.id === this.pendingCallId) : undefined;
    if (pending && (pending.state === "ended" || pending.state === "error")) {
      this.error = pending.state === "error" ? "L'appel n'a pas pu aboutir." : "L'appel s'est terminé.";
      this.teardown();
      return;
    }
    const ready = this.pendingCallId
      ? pending?.state === "streaming"
        ? pending
        : undefined
      : this.vm.streamingCall;
    if (ready) void this.negotiate(this.pendingCallId);
  }

  private async negotiate(callId: string | null): Promise<void> {
    const hass = this.hass;
    const entryId = this.entryId;
    if (!hass || !entryId || this.connecting) return;
    this.connecting = true;
    this.linkState = "negotiating";
    this.error = undefined;
    const link = new WebrtcLink(
      browserDeps,
      (stream) => this.onRemote(stream),
      (reason) => this.onDegraded(reason),
    );
    this.link = link;
    try {
      await link.connect(callId, (offer) => gw.postOffer(hass, entryId, offer, callId));
      this.sessionId = link.sessionId;
      this.linkState = this.hasRemote ? "live" : "waiting";
    } catch (error) {
      this.error = error instanceof UnsupportedCodecError ? error.message : "La connexion vidéo a échoué.";
      console.warn("urmet: negotiate failed", error);
      this.teardown();
    } finally {
      this.connecting = false;
      this.host.requestUpdate();
    }
  }

  private onRemote(stream: MediaStream): void {
    this.stream = stream;
    this.hasRemote = true;
    if (this.linkState === "negotiating" || this.linkState === "waiting") this.linkState = "live";
    this.host.requestUpdate();
  }

  private onDegraded(reason: string): void {
    this.linkState = "degraded";
    this.error = reason;
    this.host.requestUpdate();
  }

  private fail(message: string, error: unknown): void {
    this.error = message;
    console.warn("urmet:", message, error);
    this.teardown();
    this.host.requestUpdate();
  }

  private ensureRingTimer(): void {
    if (this.ringTimer) return;
    this.ringStart = Date.now();
    this.ringSeconds = 0;
    this.ringTimer = setInterval(() => {
      this.ringSeconds = Math.floor((Date.now() - (this.ringStart ?? Date.now())) / 1000);
      this.host.requestUpdate();
    }, 1000);
  }

  private stopRingTimer(): void {
    if (this.ringTimer) {
      clearInterval(this.ringTimer);
      this.ringTimer = undefined;
    }
    this.ringSeconds = 0;
    this.ringStart = undefined;
  }
}
