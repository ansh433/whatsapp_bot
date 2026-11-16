"""Meta WhatsApp Cloud API: sends messages and parses incoming webhooks.
The only file that knows Meta's payload formats."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

import config

log = logging.getLogger(__name__)

# Meta's limits for interactive messages
_BODY_MAX = 1024
_HEADER_MAX = 60
_BUTTON_MAX = 20      # list button label and reply-button titles
_SECTION_MAX = 24
_ROW_TITLE_MAX = 24
_ROW_DESC_MAX = 72


# ---------------------------------------------------------------- incoming

@dataclass
class Incoming:
    phone: str
    message_id: str
    kind: str              # "text" | "tap" | "unsupported"
    name: str = ""
    text: str = ""
    option_id: str = ""

    def preview(self) -> str:
        """Short human-readable description, used for history and staff forwarding."""
        if self.kind == "text":
            return self.text
        if self.kind == "tap":
            return f"[selected {self.option_id}]"
        return "[sent something the bot can't read, e.g. an image or voice note]"


def parse_incoming(payload: dict) -> list[Incoming]:
    """Extract customer messages from a webhook payload. Delivery/read receipts give an empty list."""
    found = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): c.get("profile", {}).get("name", "") for c in value.get("contacts", [])}
            for message in value.get("messages", []):
                found.append(_to_incoming(message, names))
    return found


def _to_incoming(message: dict, names: dict) -> Incoming:
    phone = message.get("from", "")
    base = {"phone": phone, "message_id": message.get("id", ""), "name": names.get(phone, "")}
    kind = message.get("type")
    if kind == "text":
        return Incoming(kind="text", text=message.get("text", {}).get("body", ""), **base)
    if kind == "interactive":
        interactive = message.get("interactive", {})
        reply = interactive.get(interactive.get("type", ""), {})   # list_reply / button_reply
        if reply.get("id"):
            return Incoming(kind="tap", option_id=reply["id"], **base)
    return Incoming(kind="unsupported", **base)


# ---------------------------------------------------------------- outgoing

def _post(payload: dict) -> None:
    url = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{config.PHONE_NUMBER_ID}/messages"
    response = requests.post(
        url, json=payload, headers={"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"}, timeout=15
    )
    if not response.ok:
        log.error("WhatsApp API error %s: %s", response.status_code, response.text)
        response.raise_for_status()


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def send_text(to: str, text: str) -> None:
    _post({"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}})


def send_list(to: str, body: str, button: str, section: str, rows: list[dict], header: str | None = None) -> None:
    """The dropdown: a button that opens a list of up to 10 options."""
    interactive = {
        "type": "list",
        "body": {"text": _clip(body, _BODY_MAX)},
        "action": {
            "button": _clip(button, _BUTTON_MAX),
            "sections": [
                {
                    "title": _clip(section, _SECTION_MAX),
                    "rows": [
                        {
                            "id": row["id"],
                            "title": _clip(row["title"], _ROW_TITLE_MAX),
                            **({"description": _clip(row["description"], _ROW_DESC_MAX)} if row.get("description") else {}),
                        }
                        for row in rows[:10]
                    ],
                }
            ],
        },
    }
    if header:
        interactive["header"] = {"type": "text", "text": _clip(header, _HEADER_MAX)}
    _post({"messaging_product": "whatsapp", "to": to, "type": "interactive", "interactive": interactive})


def send_buttons(to: str, body: str, buttons: list[dict]) -> None:
    """Up to 3 quick-reply buttons under a message."""
    interactive = {
        "type": "button",
        "body": {"text": _clip(body, _BODY_MAX)},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": b["id"], "title": _clip(b["title"], _BUTTON_MAX)}}
                for b in buttons[:3]
            ]
        },
    }
    _post({"messaging_product": "whatsapp", "to": to, "type": "interactive", "interactive": interactive})


def send_menu(to: str, menu: dict) -> None:
    """Send a menu built by menus.py (a dict with kind 'list' or 'buttons')."""
    if menu["kind"] == "list":
        send_list(to, menu["body"], menu["button"], menu["section"], menu["rows"], menu.get("header"))
    else:
        send_buttons(to, menu["body"], menu["buttons"])


def mark_read(message_id: str) -> None:
    """Show the blue ticks. Best effort: never lets a failure here stop the reply."""
    if not message_id:
        return
    try:
        _post({"messaging_product": "whatsapp", "status": "read", "message_id": message_id})
    except Exception:
        log.warning("mark_read failed", exc_info=True)
