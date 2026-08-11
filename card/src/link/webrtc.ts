// The card owns its WebRTC leg. Both ends are on the LAN, so the peer connection
// carries an empty iceServers list and host candidates alone negotiate; there is
// no trickle, gathering is awaited once with a hard cap, then the SDP is posted
// with its candidates in one shot (DESIGN 7.2). The uplink transceiver is
// created sendrecv with no track so the mic is added later with replaceTrack,
// which never replaces the session and never takes the picture down.

const GATHER_TIMEOUT_MS = 2000; // DESIGN 7.2: cap on ICE gathering before posting.

export class UnsupportedCodecError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UnsupportedCodecError";
  }
}

export interface WebrtcDeps {
  createPeerConnection(config: RTCConfiguration): RTCPeerConnection;
  getUserMedia(constraints: MediaStreamConstraints): Promise<MediaStream>;
}

export const browserDeps: WebrtcDeps = {
  createPeerConnection: (config) => new RTCPeerConnection(config),
  getUserMedia: (constraints) => navigator.mediaDevices.getUserMedia(constraints),
};

export type OfferPoster = (offer: RTCSessionDescriptionInit) => Promise<{
  sdp: string;
  session_id: string;
  call_id: string;
}>;

// A browser with neither H264 nor PCMA in its own offer cannot watch or speak;
// saying so beats a black pane (DESIGN 7.2).
export function offerHasRequiredCodecs(sdp: string): boolean {
  return /a=rtpmap:\d+ H264\//i.test(sdp) && /a=rtpmap:\d+ PCMA\//i.test(sdp);
}

export class WebrtcLink {
  private pc?: RTCPeerConnection;
  private audioSender?: RTCRtpSender;
  private micStream?: MediaStream;
  private micTrack?: MediaStreamTrack;
  private closed = false;

  sessionId?: string;
  callId?: string;

  constructor(
    private readonly deps: WebrtcDeps,
    private readonly onRemote: (stream: MediaStream) => void,
    private readonly onDegraded: (reason: string) => void,
  ) {}

  get hasMic(): boolean {
    return !!this.micTrack;
  }

  async connect(callId: string | null, poster: OfferPoster): Promise<void> {
    this.callId = callId ?? undefined;
    const pc = this.deps.createPeerConnection({ iceServers: [] });
    this.pc = pc;

    pc.addEventListener("track", (event) => {
      const stream = (event as RTCTrackEvent).streams?.[0];
      if (stream) this.onRemote(stream);
    });
    pc.addEventListener("connectionstatechange", () => {
      if (pc.connectionState === "failed") this.onDegraded("Connexion média perdue.");
    });

    pc.addTransceiver("video", { direction: "recvonly" });
    this.audioSender = pc.addTransceiver("audio", { direction: "sendrecv" }).sender;

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await this.waitForGathering(pc);

    const local = pc.localDescription;
    if (!local?.sdp) throw new Error("L'offre WebRTC est vide.");
    if (!offerHasRequiredCodecs(local.sdp)) {
      throw new UnsupportedCodecError(
        "Ce navigateur ne propose ni H264 ni PCMA: l'image et la voix du portier ne peuvent pas s'afficher ici.",
      );
    }

    const answer = await poster({ sdp: local.sdp, type: local.type });
    this.sessionId = answer.session_id;
    if (answer.call_id) this.callId = answer.call_id;
    await pc.setRemoteDescription({ type: "answer", sdp: answer.sdp });
  }

  async enableMic(): Promise<void> {
    if (!this.pc || !this.audioSender || this.micTrack) return;
    const stream = await this.deps.getUserMedia({ audio: true, video: false });
    this.micStream = stream;
    this.micTrack = stream.getAudioTracks()[0];
    await this.audioSender.replaceTrack(this.micTrack);
  }

  setMicEnabled(enabled: boolean): void {
    if (this.micTrack) this.micTrack.enabled = enabled;
  }

  // Called on every exit path. The Android companion app leaves the microphone
  // hardware-locked when the app cleanup is trusted, so every track is stopped
  // here rather than relying on the app (best-practices-card section 6).
  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.micStream?.getTracks().forEach((track) => track.stop());
    this.micStream = undefined;
    this.micTrack = undefined;
    const pc = this.pc;
    if (pc) {
      pc.getReceivers().forEach((receiver) => receiver.track?.stop());
      pc.close();
    }
    this.pc = undefined;
    this.audioSender = undefined;
  }

  private waitForGathering(pc: RTCPeerConnection): Promise<void> {
    if (pc.iceGatheringState === "complete") return Promise.resolve();
    return new Promise((resolve) => {
      let timer: ReturnType<typeof setTimeout>;
      const finish = (): void => {
        clearTimeout(timer);
        pc.removeEventListener("icegatheringstatechange", onChange);
        resolve();
      };
      const onChange = (): void => {
        if (pc.iceGatheringState === "complete") finish();
      };
      timer = setTimeout(finish, GATHER_TIMEOUT_MS);
      pc.addEventListener("icegatheringstatechange", onChange);
    });
  }
}
