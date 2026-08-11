import { describe, expect, it, vi } from "vitest";
import {
  offerHasRequiredCodecs,
  UnsupportedCodecError,
  type WebrtcDeps,
  WebrtcLink,
} from "../src/link/webrtc";

const GOOD_SDP =
  "v=0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\na=rtpmap:96 H264/90000\r\nm=audio 9 UDP/TLS/RTP/SAVPF 8\r\na=rtpmap:8 PCMA/8000\r\n";
const BAD_SDP = "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=rtpmap:111 opus/48000\r\n";

function makeFakePc(sdp: string) {
  const listeners: Record<string, ((event?: unknown) => void)[]> = {};
  const sender = { replaceTrack: vi.fn().mockResolvedValue(undefined) };
  const receiverTrack = { stop: vi.fn() };
  const pc = {
    iceGatheringState: "complete" as RTCIceGatheringState,
    connectionState: "connected" as RTCPeerConnectionState,
    localDescription: null as RTCSessionDescription | null,
    close: vi.fn(),
    addEventListener: (type: string, cb: (event?: unknown) => void) => {
      listeners[type] ??= [];
      listeners[type].push(cb);
    },
    removeEventListener: (type: string, cb: (event?: unknown) => void) => {
      listeners[type] = (listeners[type] ?? []).filter((entry) => entry !== cb);
    },
    addTransceiver: () => ({ sender }),
    createOffer: async () => ({ type: "offer", sdp }),
    setLocalDescription: async (desc: { type?: string }) => {
      pc.localDescription = { type: desc?.type ?? "offer", sdp } as RTCSessionDescription;
    },
    setRemoteDescription: vi.fn().mockResolvedValue(undefined),
    getReceivers: () => [{ track: receiverTrack }],
    fire: (type: string, event?: unknown) => {
      for (const cb of listeners[type] ?? []) cb(event);
    },
    sender,
    receiverTrack,
  };
  return pc;
}

function makeMic() {
  const track = { stop: vi.fn(), enabled: true, kind: "audio" };
  const stream = { getAudioTracks: () => [track], getTracks: () => [track] };
  return { track, stream };
}

function deps(pc: ReturnType<typeof makeFakePc>, mic: ReturnType<typeof makeMic>): WebrtcDeps {
  return {
    createPeerConnection: () => pc as unknown as RTCPeerConnection,
    getUserMedia: async () => mic.stream as unknown as MediaStream,
  };
}

describe("offerHasRequiredCodecs", () => {
  it("requires both H264 and PCMA", () => {
    expect(offerHasRequiredCodecs(GOOD_SDP)).toBe(true);
    expect(offerHasRequiredCodecs(BAD_SDP)).toBe(false);
    expect(offerHasRequiredCodecs("a=rtpmap:96 H264/90000")).toBe(false);
  });
});

describe("WebrtcLink.connect", () => {
  it("negotiates, posts the offer, applies the answer and delivers the remote stream", async () => {
    const pc = makeFakePc(GOOD_SDP);
    const mic = makeMic();
    let remote: MediaStream | undefined;
    const link = new WebrtcLink(
      deps(pc, mic),
      (stream) => {
        remote = stream;
      },
      () => undefined,
    );
    const poster = vi
      .fn()
      .mockResolvedValue({ sdp: "answer-sdp", session_id: "sess-1", call_id: "call-9" });

    await link.connect("call-9", poster);

    expect(poster).toHaveBeenCalledOnce();
    expect(poster.mock.calls[0][0]).toMatchObject({ type: "offer", sdp: GOOD_SDP });
    expect(pc.setRemoteDescription).toHaveBeenCalledWith({ type: "answer", sdp: "answer-sdp" });
    expect(link.sessionId).toBe("sess-1");
    expect(link.callId).toBe("call-9");

    pc.fire("track", { streams: [{ id: "remote" } as unknown as MediaStream] });
    expect(remote).toEqual({ id: "remote" });

    await link.enableMic();
    expect(pc.sender.replaceTrack).toHaveBeenCalledWith(mic.track);
    expect(link.hasMic).toBe(true);
  });

  it("refuses an offer that carries neither H264 nor PCMA", async () => {
    const pc = makeFakePc(BAD_SDP);
    const link = new WebrtcLink(
      deps(pc, makeMic()),
      () => undefined,
      () => undefined,
    );
    await expect(link.connect(null, vi.fn())).rejects.toBeInstanceOf(UnsupportedCodecError);
  });
});

describe("WebrtcLink.close", () => {
  it("stops every track and closes the peer connection, idempotently", async () => {
    const pc = makeFakePc(GOOD_SDP);
    const mic = makeMic();
    const link = new WebrtcLink(
      deps(pc, mic),
      () => undefined,
      () => undefined,
    );
    await link.connect(null, vi.fn().mockResolvedValue({ sdp: "a", session_id: "s", call_id: "" }));
    await link.enableMic();

    link.close();
    link.close();

    expect(mic.track.stop).toHaveBeenCalledTimes(1);
    expect(pc.receiverTrack.stop).toHaveBeenCalledTimes(1);
    expect(pc.close).toHaveBeenCalledTimes(1);
  });
});
