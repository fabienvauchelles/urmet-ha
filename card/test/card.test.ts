// @vitest-environment jsdom
import { beforeAll, describe, expect, it, vi } from "vitest";
import "../src/index";
import type { HomeAssistant } from "../src/state";

type Card = HTMLElement & {
  setConfig(config: Record<string, unknown>): void;
  hass: HomeAssistant;
  _link: Record<string, unknown> & { stream?: unknown };
  _videoRef: { value?: unknown };
  _assignStream(): void;
  disconnectedCallback(): void;
  requestUpdate(): void;
  updateComplete: Promise<boolean>;
  shadowRoot: ShadowRoot | null;
};

const CAM = { entity_id: "camera.preview", state: "idle", attributes: { access_token: "tok" } };

function makeHass(extra: Record<string, unknown> = {}, camera: unknown = CAM): HomeAssistant {
  return {
    states: { "camera.preview": camera, ...extra } as HomeAssistant["states"],
    entities: {},
    connection: { subscribeMessage: async () => async () => {} },
    callWS: vi.fn().mockResolvedValue({}),
    callService: vi.fn().mockResolvedValue(undefined),
  } as unknown as HomeAssistant;
}

function create(): Card {
  return document.createElement("urmet-portier-card") as Card;
}

describe("registration", () => {
  it("registers the custom element and the picker entry", () => {
    expect(customElements.get("urmet-portier-card")).toBeTruthy();
    expect(customElements.get("urmet-portier-card-editor")).toBeTruthy();
    const cards = (window as unknown as { customCards: { type: string }[] }).customCards;
    expect(cards.some((entry) => entry.type === "urmet-portier-card")).toBe(true);
  });
});

describe("setConfig", () => {
  it("throws on an unknown key", () => {
    const el = create();
    expect(() => el.setConfig({ type: "custom:urmet-portier-card", bogus: 1 })).toThrow();
  });
  it("throws on an invalid auto_start", () => {
    const el = create();
    expect(() => el.setConfig({ type: "custom:urmet-portier-card", auto_start: "sometimes" })).toThrow();
  });
  it("accepts the documented keys and HA layout keys", () => {
    const el = create();
    expect(() =>
      el.setConfig({
        type: "custom:urmet-portier-card",
        entry_id: "e1",
        auto_start: "always",
        preview_camera: "camera.preview",
        show_tech: false,
        grid_options: { rows: 8 },
      }),
    ).not.toThrow();
  });
});

describe("hass diffing", () => {
  it("does not re-render on a tick that leaves the tracked entities unchanged", () => {
    const el = create();
    el.setConfig({ type: "custom:urmet-portier-card", entry_id: "e1", preview_camera: "camera.preview" });
    el.hass = makeHass();
    const spy = vi.spyOn(el, "requestUpdate");
    el.hass = makeHass({ "light.random": { entity_id: "light.random", state: "on", attributes: {} } });
    expect(spy).not.toHaveBeenCalled();
    // positive control: a fresh camera state object is a real change
    el.hass = makeHass({}, { ...CAM });
    expect(spy).toHaveBeenCalled();
  });
});

describe("video element", () => {
  it("assigns srcObject only when the stream reference changes, never on unrelated calls", () => {
    const el = create();
    el.setConfig({ type: "custom:urmet-portier-card", entry_id: "e1" });
    el.hass = makeHass();
    const video = { srcObject: null as unknown, muted: false, play: () => Promise.resolve() };
    el._videoRef.value = video;
    const stream = { id: "remote" };
    el._link.stream = stream;

    el._assignStream();
    expect(video.srcObject).toBe(stream);

    // a second call with the same stream must not touch the element
    video.muted = false;
    el._assignStream();
    expect(video.muted).toBe(false);
    expect(video.srcObject).toBe(stream);

    el._link.stream = undefined;
    el._assignStream();
    expect(video.srcObject).toBe(null);
  });
});

describe("teardown", () => {
  let el: Card;
  let hass: HomeAssistant;
  const closeSpy = vi.fn();
  const unsubSpy = vi.fn().mockResolvedValue(undefined);

  beforeAll(() => {
    el = create();
    el.setConfig({ type: "custom:urmet-portier-card", entry_id: "e1" });
    hass = makeHass();
    el.hass = hass;
    el._link.link = { close: closeSpy };
    el._link.sessionId = "sess-1";
    el._link.entryId = "e1";
    el._link.unsub = unsubSpy;
    el.disconnectedCallback();
  });

  it("closes the WebRTC leg", () => {
    expect(closeSpy).toHaveBeenCalled();
  });
  it("unsubscribes from the gateway", () => {
    expect(unsubSpy).toHaveBeenCalled();
  });
  it("closes the media session over the WebSocket", () => {
    expect(hass.callWS).toHaveBeenCalledWith(
      expect.objectContaining({ type: "urmet/webrtc/close", entry_id: "e1", session_id: "sess-1" }),
    );
  });
});

describe("ring handling", () => {
  function connect(config: Record<string, unknown>) {
    let deliver: ((frame: unknown) => void) | undefined;
    const hass = makeHass();
    hass.connection.subscribeMessage = ((cb: (f: unknown) => void) => {
      deliver = cb;
      return Promise.resolve(async () => {});
    }) as never;
    const el = create();
    el.setConfig({ type: "custom:urmet-portier-card", entry_id: "e1", ...config });
    document.body.appendChild(el);
    el.hass = hass;
    return { el, hass, deliver: () => deliver };
  }

  const ring = (direction: string) => ({
    type: "state",
    registered: true,
    doorphone: null,
    mic_muted: true,
    sessions: [],
    calls: [{ id: "c1", state: "ringing", direction }],
  });

  it("never answers a ring on its own; the visitor is shown for a manual answer", async () => {
    const { el, hass, deliver } = connect({ auto_start: "on_ring" });
    deliver()?.(ring("incoming"));
    await Promise.resolve();
    expect(hass.callService).not.toHaveBeenCalledWith("urmet", "answer", expect.anything());
    expect((el._link as { vm: { ringingCall?: { id: string } } }).vm.ringingCall?.id).toBe("c1");
    el.remove();
  });
});
