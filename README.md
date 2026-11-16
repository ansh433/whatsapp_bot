# Glow Studio: WhatsApp Booking Bot

A WhatsApp appointment bot for a salon. Customers book, check and cancel appointments
by tapping a **dropdown menu**, or by simply typing what they want ("book a haircut tomorrow at 6pm").

Built with the Meta WhatsApp Cloud API, Gemini, FastAPI and Google Sheets.

## What it does

| Feature | How the customer uses it |
|---|---|
| Main menu dropdown | Say "Hi" and tap **View options** |
| Book an appointment | Service, then day, then time slot (all dropdowns), then Confirm |
| Natural-language booking | Type "haircut tomorrow evening"; the bot fills in what it understood and dropdowns ask for the rest |
| Check my booking | Looks up bookings by the customer's phone number |
| Cancel | One tap on the booking card; the slot is free again |
| Services & prices, salon info | One tap |
| Talk to staff | Hands the chat to a human and notifies the staff number |

Every booking appears live in a Google Sheet, so the owner can see and edit them with no admin panel.

## How it works

Taps (dropdown and buttons) are handled by plain code. Only typed text goes to Gemini,
and Gemini only chooses an action and its inputs; the bot's own code validates them and sends every message.

```
WhatsApp -> main.py -> router.py -> tap?   flows.py
                                 -> text?  llm.py -> tools.py -> flows.py
flows.py -> menus.py (build dropdown) -> whatsapp.py (send)
        -> sheets.py / session.py / history.py / handoff.py
```

| File | Responsibility |
|---|---|
| `main.py` | HTTP endpoints for Meta's webhook |
| `router.py` | Picks the handler for each message |
| `flows.py` | The booking, check, cancel and handoff conversation steps |
| `menus.py` | Builds dropdown and button layouts |
| `whatsapp.py` | Sends messages to Meta, parses incoming webhooks |
| `llm.py` | Gemini: typed text in, chosen action out |
| `tools.py` | The five actions Gemini can pick, with argument checks |
| `schedule.py` | Opening hours, 1-hour slots, which times are free |
| `sheets.py` | Google Sheets read/write |
| `session.py` | A customer's half-finished booking |
| `history.py` | Recent chat messages (LLM context) |
| `handoff.py` | Human-handoff flag and staff notifications |
| `db.py` | Opens the local SQLite database |
| `config.py` | Settings and salon constants |

## Setup

Requires Python 3.10+.

**1. Install**
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

**2. WhatsApp (Meta)**
1. Create an app at developers.facebook.com (type Business) and add the **WhatsApp** product.
2. On **API Setup**, copy the temporary access token and the Phone number ID into `.env`.
3. Add your own number (and the staff number) as recipients and verify them.

**3. Google Sheet**
1. Create a Google Cloud project, enable the **Google Sheets API**, and create a **service account**. Download its JSON key as `service_account.json` in this folder.
2. Create an empty Google Sheet, share it with the service account's email (Editor), and put the sheet ID in `.env`.
3. Run `python setup_sheet.py` to create the `Services` and `Bookings` tabs.

**4. Gemini**
Create a key in Google AI Studio and put it in `.env` as `GEMINI_API_KEY`.

**5. Run**
```bash
uvicorn main:app --port 8000
ngrok http 8000
```
In Meta's **WhatsApp > Configuration**, set the callback URL to `https://<your-ngrok-id>.ngrok-free.app/webhook`,
the verify token to your `VERIFY_TOKEN`, then subscribe to **messages**.

## Demo script

1. Send "Hi" and open the dropdown.
2. Book through the dropdowns: Book appointment, service, day, time, Confirm. Watch the row appear in the Sheet.
3. Tap **Check my booking**, then **Cancel booking**. Watch the status change in the Sheet.
4. Type "book a facial tomorrow at 4pm" and see it jump straight to the confirmation.
5. Tap **Talk to staff** and see the staff phone get the handoff. Send `resume` from the staff number to switch the bot back on.

## Roadmap

Online payments, multiple stylists and branches, reminder messages, multiple languages,
and free-form questions about services and hours answered by the LLM.
