"""HTTP endpoints only. Receives Meta's webhook calls and hands messages to the router."""
import logging

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

import config
import router
import whatsapp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Glow Studio WhatsApp bot")


@app.get("/")
def health() -> dict:
    return {"status": "ok", "bot": config.SALON_NAME}


@app.get("/webhook")
def verify_webhook(request: Request) -> PlainTextResponse:
    """Meta calls this once when you register the webhook URL."""
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == config.VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge", ""))
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive_webhook(request: Request, background: BackgroundTasks) -> dict:
    """Meta calls this for every customer message. Reply 200 fast; do the work in the background."""
    payload = await request.json()
    for message in whatsapp.parse_incoming(payload):
        background.add_task(router.handle_incoming, message)
    return {"status": "ok"}
