"""Decides which handler gets each incoming message. Taps never touch the LLM; typed text does.

    handoff on?   -> stay silent, pass the message to staff
    tapped?       -> handle_tap   (plain code)
    typed?        -> handle_text  (LLM picks a tool)
    anything else -> handle_unsupported
Anything unrecognised ends at the main menu, never a dead end.
"""
import logging

import config
import flows
import handoff
import history
import llm
import tools
import whatsapp

log = logging.getLogger(__name__)

GREETINGS = {"hi", "hii", "hello", "hey", "hola", "menu", "start", "help"}
YES_WORDS = {"yes", "y", "yep", "yeah", "ok", "okay", "confirm", "sure"}


def handle_incoming(msg: whatsapp.Incoming) -> None:
    try:
        _dispatch(msg)
    except Exception:
        log.exception("Failed while handling a message from %s", msg.phone)
        try:
            flows.show_main_menu(msg.phone, intro="Sorry, something went wrong on our side. Here's the menu:")
        except Exception:
            log.exception("Could not send the fallback menu either")


def _dispatch(msg: whatsapp.Incoming) -> None:
    whatsapp.mark_read(msg.message_id)

    if _is_staff_resume(msg):
        return _resume(msg)
    if handoff.is_handoff(msg.phone):
        return handoff.relay_to_staff(msg.phone, msg.name, msg.preview())

    if msg.kind == "tap":
        handle_tap(msg)
    elif msg.kind == "text":
        handle_text(msg)
    else:
        handle_unsupported(msg)


# ---------------------------------------------------------------- staff command

def _is_staff_resume(msg: whatsapp.Incoming) -> bool:
    return (
        bool(config.STAFF_NUMBER)
        and msg.phone == config.STAFF_NUMBER
        and msg.kind == "text"
        and msg.text.strip().lower().startswith("resume")
    )


def _resume(msg: whatsapp.Incoming) -> None:
    """Staff sends 'resume' (most recent handoff) or 'resume 919876543210'."""
    argument = "".join(ch for ch in msg.text[len("resume"):] if ch.isdigit())
    phone = handoff.resume(argument or None)
    if phone is None:
        whatsapp.send_text(msg.phone, "No active handoff to resume.")
        return
    whatsapp.send_text(msg.phone, f"Bot resumed for +{phone}.")
    flows.show_main_menu(phone, intro="We're back! How can we help you?")


# ---------------------------------------------------------------- taps (no LLM)

def handle_tap(msg: whatsapp.Incoming) -> None:
    phone, option = msg.phone, msg.option_id
    history.save_message(phone, "user", msg.preview())

    if option == "menu_book":
        flows.start_booking(phone, fresh=True)
    elif option == "menu_check":
        flows.show_my_bookings(phone)
    elif option == "menu_services":
        flows.show_services(phone)
    elif option == "menu_info":
        flows.show_info(phone)
    elif option == "menu_staff":
        flows.go_to_staff(phone, msg.name, "Customer tapped Talk to staff")
    elif option == "confirm_yes":
        flows.confirm(phone, msg.name)
    elif option == "confirm_change":
        flows.change_booking(phone)
    elif option.startswith("svc_"):
        flows.on_service(phone, option[len("svc_"):])
    elif option.startswith("date_"):
        flows.on_date(phone, option[len("date_"):])
    elif option.startswith("slot_"):
        _, date, time = option.split("_", 2)
        flows.on_slot(phone, date, time)
    elif option.startswith("cancel_"):
        flows.cancel(phone, option[len("cancel_"):])
    else:   # menu_main, or an old menu whose option no longer exists
        flows.show_main_menu(phone)


# ---------------------------------------------------------------- typed text (LLM)

def handle_text(msg: whatsapp.Incoming) -> None:
    phone, text = msg.phone, msg.text.strip()
    past = history.get_history(phone)
    history.save_message(phone, "user", text)

    word = text.lower().strip("!.? ")
    if word in GREETINGS:
        return flows.show_main_menu(phone)
    if word in YES_WORDS and flows.has_pending_confirmation(phone):
        return flows.confirm(phone, msg.name)

    try:
        call = llm.understand(text, past, tools.build_context(phone))
    except Exception:
        log.exception("LLM call failed; falling back to the menu")
        call = None

    if call is None or not tools.run_tool(msg, call["name"], call["args"]):
        flows.show_main_menu(phone)


# ---------------------------------------------------------------- everything else

def handle_unsupported(msg: whatsapp.Incoming) -> None:
    history.save_message(msg.phone, "user", msg.preview())
    flows.show_main_menu(msg.phone, intro="I can read text messages and menu taps. Here's what I can do:")
