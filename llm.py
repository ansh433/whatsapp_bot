"""Gemini: turns a typed message into a chosen tool and its arguments.
It never writes replies and never touches storage; the bot's own code does everything the customer sees."""
import logging

import config

log = logging.getLogger(__name__)

TOOL_DECLARATIONS = [
    {
        "name": "create_booking",
        "description": (
            "The customer wants to book (or is continuing a booking). Pass only what they actually said; "
            "leave out anything they did not mention. The system asks for whatever is missing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service id from the services list."},
                "date": {"type": "string", "description": "Date as YYYY-MM-DD, worked out from today's date."},
                "time": {"type": "string", "description": "Start time, 24-hour HH:MM, e.g. 18:00 for 6 PM."},
            },
        },
    },
    {
        "name": "get_slots",
        "description": "The customer asks what times are free or available, e.g. 'anything open on Friday?'.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date as YYYY-MM-DD."},
                "service": {"type": "string", "description": "Service id, if they mentioned one."},
            },
        },
    },
    {
        "name": "check_booking",
        "description": "The customer wants to see their existing booking(s).",
    },
    {
        "name": "cancel_booking",
        "description": "The customer wants to cancel a booking. Include the booking id (like GS-1042) only if they gave it.",
        "parameters": {
            "type": "object",
            "properties": {"booking_id": {"type": "string", "description": "Booking id, e.g. GS-1042."}},
        },
    },
    {
        "name": "handoff_to_staff",
        "description": (
            "Hand the chat to a human: complaints, refunds, requests to talk to a person, "
            "or anything that is not about bookings."
        ),
        "parameters": {
            "type": "object",
            "properties": {"reason": {"type": "string", "description": "One short sentence on why."}},
            "required": ["reason"],
        },
    },
]


def build_prompt(context: dict) -> str:
    """context: {'now': datetime, 'services': [...], 'draft': {...}, 'dates': ['YYYY-MM-DD', ...]}"""
    now = context["now"]
    services = "\n".join(f"- {s['id']}: {s['name']} (₹{s['price']})" for s in context["services"])
    draft = ", ".join(f"{k}={v}" for k, v in context["draft"].items()) or "none"
    dates = context["dates"]
    return f"""You are the booking assistant for {config.SALON_NAME}, a salon, chatting on WhatsApp.
Your ONLY job is to choose the right tool for the customer's latest message. Do not write a reply:
the system sends every message the customer sees.

Right now it is {now.strftime('%A, %d %B %Y, %I:%M %p')} India time (today is {now.date().isoformat()}).
The salon is open every day, {config.OPEN_HOUR:02d}:00 to {config.CLOSE_HOUR:02d}:00, in 1-hour slots.
Bookable dates: {dates[0]} to {dates[-1]}.

Services (use the id):
{services}

Booking in progress for this customer: {draft}

Rules:
- Wants to book, even with little detail -> create_booking with only what they said. Never guess missing details.
- A follow-up like "make it 6pm" or "tomorrow" while a booking is in progress -> create_booking with just the new detail.
- Asks what is free or available -> get_slots.
- Asks about their booking -> check_booking. Wants to cancel -> cancel_booking.
- Complaint, refund, wants a person, or anything not about bookings -> handoff_to_staff.
- Greeting, thanks, or unclear -> call no tool.
- Dates must be YYYY-MM-DD; times must be 24-hour HH:MM."""


_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def understand(text: str, history: list[dict], context: dict) -> dict | None:
    """Return {'name': tool_name, 'args': {...}}, or None if no tool fits."""
    from google.genai import types

    contents = []
    for item in history:
        role = "user" if item["role"] == "user" else "model"
        if not contents and role == "model":
            continue   # conversations sent to Gemini should start with the user
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=item["text"])]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=text)]))

    response = _get_client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=build_prompt(context),
            tools=[types.Tool(function_declarations=TOOL_DECLARATIONS)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )

    for candidate in response.candidates or []:
        parts = candidate.content.parts if candidate.content and candidate.content.parts else []
        for part in parts:
            if part.function_call:
                call = part.function_call
                return {"name": call.name, "args": dict(call.args or {})}
    return None
