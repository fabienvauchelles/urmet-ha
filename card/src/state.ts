// The view model and every shared type. This module is the innermost layer:
// it imports nothing from the project and touches no DOM, so the link and view
// layers can depend on it without dragging Lit or the browser into pure logic.
// The wire types mirror the integration's models.py (DESIGN 5.2, 5.3).

export type AutoStart = "on_ring" | "always" | "never";

// The single source of the auto_start vocabulary: the setConfig validation list,
// the editor dropdown options and every default read the same tuple and literal,
// so a mode added here cannot drift out of the UI or the guard.
export const AUTO_START_MODES: readonly AutoStart[] = ["on_ring", "always", "never"];
export const DEFAULT_AUTO_START: AutoStart = "on_ring";

export interface UrmetCardConfig {
  type: string;
  entry_id?: string;
  auto_start?: AutoStart;
  preview_camera?: string;
  show_tech?: boolean;
  // Home Assistant writes these onto the card config when the user resizes or
  // places the card; they are not ours but must not make setConfig throw.
  grid_options?: unknown;
  layout_options?: unknown;
  view_layout?: unknown;
}

// The card's own signalling leg, distinct from the gateway call state.
export type LinkState = "idle" | "answering" | "negotiating" | "waiting" | "live" | "degraded";

// A camera to show behind the ring and the stage until the WebRTC leg is live is
// optional and set per card through the `preview_camera` config key; with none
// set the stage shows a neutral placeholder instead of any specific entity.

// --- Minimal Home Assistant surface the card actually uses ------------------

export interface HassEntityState {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
}

export interface HassEntityRegistryEntry {
  entity_id: string;
  platform?: string;
  config_entry_id?: string | null;
  device_id?: string | null;
}

// The device registry entry, the only reliable place to read a config entry id:
// the frontend entity registry drops config_entry_id on some Home Assistant
// builds, but the device always carries the entry that owns it.
export interface HassDeviceRegistryEntry {
  id: string;
  primary_config_entry?: string | null;
  config_entries?: string[];
}

export type UnsubscribeFunc = () => Promise<void>;

export interface HassConnection {
  subscribeMessage<T>(
    callback: (message: T) => void,
    subscription: Record<string, unknown>,
  ): Promise<UnsubscribeFunc>;
}

export interface HomeAssistant {
  states: Record<string, HassEntityState>;
  entities: Record<string, HassEntityRegistryEntry>;
  devices?: Record<string, HassDeviceRegistryEntry>;
  connection: HassConnection;
  callWS<T>(message: Record<string, unknown>): Promise<T>;
  callService(domain: string, service: string, data?: Record<string, unknown>): Promise<unknown>;
}

// --- Gateway wire model (DESIGN 5.2) ---------------------------------------

export interface DoorphoneWire {
  mac: string;
  name: string;
}

// The gateway's own call and session vocabulary, spelled out rather than typed
// as string: a comparison against a value the gateway never sends is a compile
// error here, the way it is an enum mismatch in the gateway and the integration.
export type CallStateWire = "idle" | "ringing" | "connecting" | "streaming" | "ended" | "error";
export type CallDirectionWire = "incoming" | "outgoing";
export type SessionStateWire = "open" | "waiting" | "degraded" | "closed";

export interface CallWire {
  id: string;
  state: CallStateWire;
  direction: CallDirectionWire;
}

export interface VideoStatsWire {
  width: number;
  height: number;
  packets_sent: number;
  packets_dropped: number;
}

// Every counter the gateway publishes, in its order. The three partial/dropped
// readings are the ones that say a voice path is losing frames rather than
// merely carrying few, so the panel must be able to show them.
export interface AudioStatsWire {
  from_doorphone: number;
  to_browser: number;
  to_doorphone: number;
  silence_sent: number;
  partial_from_doorphone: number;
  dropped_from_doorphone: number;
  dropped_to_doorphone: number;
  max_callback_ms: number;
  budget_ms: number;
}

export interface SessionWire {
  session_id: string;
  call_id: string;
  state: SessionStateWire;
  connection: string;
  reason: string;
  video: VideoStatsWire | null;
  audio: AudioStatsWire | null;
}

export interface StateWire {
  registered: boolean;
  doorphone: DoorphoneWire | null;
  calls: CallWire[];
  mic_muted: boolean;
  sessions: SessionWire[];
}

// --- Derived view model ----------------------------------------------------

export interface CardViewModel {
  registered: boolean;
  doorphoneName: string;
  ringingCall?: CallWire;
  streamingCall?: CallWire;
  activeCall?: CallWire;
  micMuted: boolean;
  session?: SessionWire;
  hasPicture: boolean;
  degraded: boolean;
}

const RINGING: CallStateWire = "ringing";
const CONNECTING: CallStateWire = "connecting";
const STREAMING: CallStateWire = "streaming";
const INCOMING: CallDirectionWire = "incoming";

export function deriveViewModel(state?: StateWire): CardViewModel {
  const calls = state?.calls ?? [];
  // Only a call coming IN is a ring. A "look at the door" places an outgoing call
  // that the gateway also reports as ringing while it connects, and treating that
  // as a ring would announce the panel as if a visitor had pressed the button.
  const ringingCall = calls.find((c) => c.state === RINGING && c.direction === INCOMING);
  const streamingCall = calls.find((c) => c.state === STREAMING);
  const connectingCall = calls.find((c) => c.state === CONNECTING);
  const activeCall = streamingCall ?? connectingCall ?? ringingCall;
  const session = activeCall
    ? (state?.sessions ?? []).find((s) => s.call_id === activeCall.id)
    : undefined;
  return {
    registered: state?.registered ?? false,
    doorphoneName: state?.doorphone?.name || "Portier",
    ringingCall,
    streamingCall,
    activeCall,
    micMuted: state?.mic_muted ?? true,
    session,
    hasPicture: !!(session?.video && session.video.width > 0),
    degraded: session?.state === "degraded",
  };
}

// --- Entry resolution and change tracking ----------------------------------

// The config entry that owns an entity: its own config_entry_id when the
// frontend kept it, otherwise the entry read off the entity's device.
function entryIdForEntity(hass: HomeAssistant, entry: HassEntityRegistryEntry): string | undefined {
  if (entry.config_entry_id) return entry.config_entry_id;
  const device = entry.device_id ? hass.devices?.[entry.device_id] : undefined;
  return device?.primary_config_entry ?? device?.config_entries?.[0] ?? undefined;
}

export function findEntryIds(hass: HomeAssistant): string[] {
  const ids = new Set<string>();
  for (const entry of Object.values(hass.entities ?? {})) {
    if (entry.platform !== "urmet") continue;
    const entryId = entryIdForEntity(hass, entry);
    if (entryId) ids.add(entryId);
  }
  return [...ids];
}

export function findDoorbellEntity(hass: HomeAssistant, entryId?: string): string | undefined {
  for (const entry of Object.values(hass.entities ?? {})) {
    if (entry.platform !== "urmet") continue;
    if (entryId && entryIdForEntity(hass, entry) !== entryId) continue;
    if (entry.entity_id.startsWith("event.") && entry.entity_id.includes("doorbell"))
      return entry.entity_id;
  }
  return undefined;
}

// The three outcomes of resolving the card's entry. ``pending`` is neither a
// binding nor a fault: urmet entities exist but the device registry that
// carries their entry id has not reached the frontend yet, so the caller must
// retry on the next hass push rather than freeze an error banner.
export type EntryResolution = { entryId: string } | { error: string } | { pending: true };

export function resolveEntry(config: UrmetCardConfig, hass: HomeAssistant): EntryResolution {
  if (config.entry_id) return { entryId: config.entry_id };
  const ids = findEntryIds(hass);
  if (ids.length === 1) return { entryId: ids[0] };
  if (ids.length > 1) {
    return {
      error: "Plusieurs portiers configurés: précisez entry_id dans la configuration de la carte.",
    };
  }
  const hasEntities = Object.values(hass.entities ?? {}).some(
    (entry) => entry.platform === "urmet",
  );
  if (hasEntities) return { pending: true };
  return { error: "Aucune entrée Portier Urmet n'est configurée." };
}

export function trackedIds(config: UrmetCardConfig | undefined, doorbell?: string): string[] {
  const ids: string[] = [];
  if (config?.preview_camera) ids.push(config.preview_camera);
  if (doorbell) ids.push(doorbell);
  return ids;
}

// HA hands back a fresh state object for an entity only when it changed, so an
// identity check per tracked id tells an unrelated tick from a relevant one.
export function statesEqual(
  a: HomeAssistant | undefined,
  b: HomeAssistant | undefined,
  ids: string[],
): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  return ids.every((id) => a.states[id] === b.states[id]);
}

export function stageSentence(link: LinkState, hasPicture: boolean): string | undefined {
  if (link === "negotiating") return "Connexion à la caméra du portier…";
  if (link === "waiting") return "En attente de l'image…";
  if (link === "live" && !hasPicture) return "Le portier envoie le son sans image.";
  return undefined;
}
