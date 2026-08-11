// The ingress diagnostics panel: always on screen, never folded.
//
// It reads the same surface a Home Assistant integration reads, over relative
// URLs so it works under the ingress path prefix. The state panel is driven by
// the event stream (a state event follows every other event, so it never lags);
// the counters that only a poll carries are refreshed on a slow cadence beside it.

"use strict";

const BASE = location.pathname.replace(/\/[^/]*$/, "/");
const POLL_MS = 5000;
const LOG_MAX = 40;

const $ = (id) => document.getElementById(id);

function api(path) {
  return fetch(BASE + path, { headers: { accept: "application/json" } });
}

function dot(el, up) {
  const d = el.querySelector(".dot") || el;
  d.className = "dot " + (up ? "up" : "down");
}

function text(el, value) {
  el.textContent = value === null || value === undefined || value === "" ? "-" : String(value);
}

function rows(tbody, items, cells, emptyLabel) {
  tbody.innerHTML = "";
  if (!items || items.length === 0) {
    const tr = tbody.insertRow();
    const td = tr.insertCell();
    td.colSpan = cells(null).length || 1;
    td.className = "empty";
    td.textContent = emptyLabel;
    return;
  }
  for (const item of items) {
    const tr = tbody.insertRow();
    for (const value of cells(item)) tr.insertCell().textContent = value ?? "";
  }
}

function renderState(s) {
  dot($("reg-bound"), s.registered);
  text($("reg-code"), s.status_code);
  text($("reg-reason"), s.reason);
  text($("reg-mac"), s.doorphone ? (s.doorphone.name || s.doorphone.mac) : null);
  text($("reg-mic"), s.mic_muted ? "muted" : "open");
  rows($("calls"), s.calls, (c) => (c ? [c.id, c.state, c.direction] : ["", "", ""]), "no live call");
  rows($("sessions"), s.sessions,
    (x) => (x ? [x.session_id, x.state, x.connection, x.reason] : ["", "", "", ""]), "no session");
}

let lastReg = { status_code: 0, reason: "" };

function applyState(state) {
  renderState({ ...state, status_code: lastReg.status_code, reason: lastReg.reason });
}

function logEvent(event) {
  const tbody = $("log");
  const tr = tbody.insertRow(0);
  tr.insertCell().textContent = (event.at || "").replace("T", " ").replace("Z", "");
  tr.insertCell().textContent = event.type;
  const detail = event.reason ?? event.acknowledged ?? event.call_id ?? event.registered ?? "";
  tr.insertCell().textContent = String(detail);
  while (tbody.rows.length > LOG_MAX) tbody.deleteRow(tbody.rows.length - 1);
}

async function poll() {
  try {
    const res = await api("api/diagnostics");
    if (!res.ok) return;
    const d = await res.json();
    text($("director"), d.director_failures.count);
    text($("settings"), JSON.stringify(d.settings));
    applyState(d.state);
  } catch (_) {
    /* the stream carries the live state; a failed poll only ages the counters */
  }
}

function connect() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(proto + "//" + location.host + BASE + "api/events");
  ws.onopen = () => dot($("stream"), true);
  ws.onclose = () => { dot($("stream"), false); setTimeout(connect, 2000); };
  ws.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.type === "registration") lastReg = { status_code: event.status_code, reason: event.reason };
    if (event.type === "state") applyState(event);
    else logEvent(event);
  };
}

$("link").textContent = BASE;
connect();
poll();
setInterval(poll, POLL_MS);
