"""Read the exact payload the card sends to ``urmet/webrtc/offer``.

The card builds that message in ``card/src/link/hass.ts``. This helper parses
that TypeScript source so the integration regression test can drive the REAL
``websocket_api`` schema with the SAME keys the card sends. If the card and the
schema ever drift again (a stray ``sdp_type`` re-added, a key renamed), the
schema rejects the message and the test fails. That is the point: the card and
the WebSocket API can no longer disagree silently on this payload.
"""

from __future__ import annotations

import re
from pathlib import Path

_CARD_SOURCE = Path(__file__).resolve().parents[2] / "card" / "src" / "link" / "hass.ts"


def _offer_object_literal(source: str) -> str:
    """Return the body of the object literal ``postOffer`` passes to ``callWS``."""
    start = source.index("export function postOffer")
    call = source.index("callWS", start)
    open_brace = source.index("{", call)
    depth = 0
    for index in range(open_brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace + 1 : index]
    raise ValueError("the callWS object literal in postOffer is never closed")


def _resolve(source: str, value: str) -> str | None:
    """Resolve a literal string, or a ``const NAME = "..."`` reference, else None."""
    value = value.strip()
    if value[:1] in {'"', "'"}:
        return value[1:-1]
    match = re.search(rf'const {re.escape(value)}\s*=\s*"([^"]+)"', source)
    return match.group(1) if match else None


def card_offer_payload() -> tuple[list[str], dict[str, str]]:
    """Return the ordered payload keys and any statically resolved string values."""
    source = _CARD_SOURCE.read_text(encoding="utf-8")
    literal = _offer_object_literal(source)
    keys: list[str] = []
    resolved: dict[str, str] = {}
    for key, raw_value in re.findall(r"(\w+)\s*:\s*([^,\n]+)", literal):
        keys.append(key)
        value = _resolve(source, raw_value)
        if value is not None:
            resolved[key] = value
    return keys, resolved
