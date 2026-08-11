import { describe, expect, it } from "vitest";
import {
  deriveViewModel,
  findEntryIds,
  resolveEntry,
  stageSentence,
  statesEqual,
  trackedIds,
  type HomeAssistant,
  type StateWire,
} from "../src/state";

function hass(entities: HomeAssistant["entities"], states: HomeAssistant["states"] = {}): HomeAssistant {
  return {
    states,
    entities,
    connection: { subscribeMessage: async () => async () => {} },
    callWS: async () => ({}) as never,
    callService: async () => undefined,
  };
}

describe("deriveViewModel", () => {
  it("detects a ringing call with no picture", () => {
    const state: StateWire = {
      registered: true,
      doorphone: { mac: "00", name: "Portail" },
      calls: [{ id: "c1", state: "ringing", direction: "in" }],
      mic_muted: true,
      sessions: [],
    };
    const vm = deriveViewModel(state);
    expect(vm.ringingCall?.id).toBe("c1");
    expect(vm.activeCall?.id).toBe("c1");
    expect(vm.streamingCall).toBeUndefined();
    expect(vm.hasPicture).toBe(false);
    expect(vm.doorphoneName).toBe("Portail");
  });

  it("binds a streaming call to its session and reads the picture", () => {
    const state: StateWire = {
      registered: true,
      doorphone: null,
      calls: [{ id: "c9", state: "streaming", direction: "in" }],
      mic_muted: false,
      sessions: [
        {
          session_id: "s1",
          call_id: "c9",
          state: "open",
          connection: "connected",
          reason: "",
          video: { width: 656, height: 656, packets_sent: 10, packets_dropped: 0 },
          audio: null,
        },
      ],
    };
    const vm = deriveViewModel(state);
    expect(vm.streamingCall?.id).toBe("c9");
    expect(vm.session?.session_id).toBe("s1");
    expect(vm.hasPicture).toBe(true);
    expect(vm.degraded).toBe(false);
  });

  it("marks a degraded session", () => {
    const vm = deriveViewModel({
      registered: true,
      doorphone: null,
      calls: [{ id: "c1", state: "streaming", direction: "in" }],
      mic_muted: false,
      sessions: [
        { session_id: "s1", call_id: "c1", state: "degraded", connection: "failed", reason: "x", video: null, audio: null },
      ],
    });
    expect(vm.degraded).toBe(true);
  });

  it("defaults gracefully with no state", () => {
    const vm = deriveViewModel(undefined);
    expect(vm.registered).toBe(false);
    expect(vm.micMuted).toBe(true);
    expect(vm.doorphoneName).toBe("Portier");
  });
});

describe("resolveEntry", () => {
  const single = { "event.portier_sonnette": { entity_id: "event.portier_sonnette", platform: "urmet", config_entry_id: "e1" } };
  const dual = {
    ...single,
    "event.autre_sonnette": { entity_id: "event.autre_sonnette", platform: "urmet", config_entry_id: "e2" },
  };

  it("uses an explicit entry_id", () => {
    expect(resolveEntry({ type: "x", entry_id: "chosen" }, hass({}))).toEqual({ entryId: "chosen" });
  });

  it("finds the single entry when none is configured", () => {
    expect(resolveEntry({ type: "x" }, hass(single))).toEqual({ entryId: "e1" });
    expect(findEntryIds(hass(single))).toEqual(["e1"]);
  });

  it("reports an error when several entries exist without entry_id", () => {
    const result = resolveEntry({ type: "x" }, hass(dual));
    expect("error" in result).toBe(true);
  });

  it("reports an error when no entry exists", () => {
    const result = resolveEntry({ type: "x" }, hass({}));
    expect("error" in result).toBe(true);
  });
});

describe("statesEqual and trackedIds", () => {
  const cam = { entity_id: "camera.frontyard", state: "idle", attributes: {} };
  it("is stable when the tracked entity keeps its identity", () => {
    const a = hass({}, { "camera.frontyard": cam });
    const b = hass({}, { "camera.frontyard": cam, "light.x": { entity_id: "light.x", state: "on", attributes: {} } });
    expect(statesEqual(a, b, trackedIds({ type: "x" }))).toBe(true);
  });
  it("differs when the tracked entity changes identity", () => {
    const a = hass({}, { "camera.frontyard": cam });
    const b = hass({}, { "camera.frontyard": { ...cam } });
    expect(statesEqual(a, b, trackedIds({ type: "x" }))).toBe(false);
  });
});

describe("stageSentence", () => {
  it("speaks during connection and audio-only, stays silent when the picture is up", () => {
    expect(stageSentence("negotiating", false)).toContain("Connexion");
    expect(stageSentence("waiting", false)).toContain("attente");
    expect(stageSentence("live", false)).toContain("son sans image");
    expect(stageSentence("live", true)).toBeUndefined();
    expect(stageSentence("idle", false)).toBeUndefined();
  });
});
