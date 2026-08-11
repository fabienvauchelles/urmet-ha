// Every call the card makes onto Home Assistant, in one place. Signalling goes
// over hass.callWS to the integration's own WebSocket commands (DESIGN 6.6);
// commands go over hass.callService to the urmet services (DESIGN 6.5). Media
// never travels here: it goes browser to add-on over LAN ICE (link/webrtc.ts).

import type { HomeAssistant, StateWire, UnsubscribeFunc } from "../state";

const WS_SUBSCRIBE = "urmet/subscribe";
const WS_OFFER = "urmet/webrtc/offer";
const WS_CLOSE = "urmet/webrtc/close";

export interface OfferReply {
  session_id: string;
  call_id: string;
  type: string;
  sdp: string;
}

interface WireFrame {
  type?: string;
}

// The subscription pushes one `state` frame on connect, then every gateway
// event; a `state` frame follows every other event (DESIGN 5.3), so the card
// converges on the full picture by consuming `state` frames alone.
export function subscribeState(
  hass: HomeAssistant,
  entryId: string,
  onState: (state: StateWire) => void,
): Promise<UnsubscribeFunc> {
  return hass.connection.subscribeMessage<WireFrame>(
    (frame) => {
      if (frame && frame.type === "state") onState(frame as unknown as StateWire);
    },
    { type: WS_SUBSCRIBE, entry_id: entryId },
  );
}

// The WS command's own `type` is the route name, so the SDP kind is not sent on
// the wire: the offer handler always treats the body as an offer and injects
// type "offer" when proxying to the gateway (DESIGN 5.2, 6.6). The WS schema
// forbids unexpected keys, so sending an extra one would be rejected. The
// reply's `type` is "answer".
export function postOffer(
  hass: HomeAssistant,
  entryId: string,
  offer: RTCSessionDescriptionInit,
  callId: string | null,
): Promise<OfferReply> {
  return hass.callWS<OfferReply>({
    type: WS_OFFER,
    entry_id: entryId,
    sdp: offer.sdp,
    call_id: callId,
  });
}

export function closeSession(
  hass: HomeAssistant,
  entryId: string,
  sessionId: string,
): Promise<unknown> {
  return hass.callWS({ type: WS_CLOSE, entry_id: entryId, session_id: sessionId });
}

export function answerCall(hass: HomeAssistant, callId?: string): Promise<unknown> {
  return hass.callService("urmet", "answer", callId ? { call_id: callId } : {});
}

export function hangUp(hass: HomeAssistant, callId?: string): Promise<unknown> {
  return hass.callService("urmet", "hang_up", callId ? { call_id: callId } : {});
}

export function look(hass: HomeAssistant): Promise<unknown> {
  return hass.callService("urmet", "look", { want_video: true });
}

export function setMic(hass: HomeAssistant, muted: boolean): Promise<unknown> {
  return hass.callService("urmet", "set_microphone", { muted });
}
