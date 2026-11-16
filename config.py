"""Settings. The only file that reads the environment or holds salon constants."""
import os

from dotenv import load_dotenv

load_dotenv()

# --- WhatsApp (Meta Cloud API) ---
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "glow-verify")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v24.0")
# Digits only, with country code, no "+" (e.g. 919876543210)
STAFF_NUMBER = os.getenv("STAFF_NUMBER", "").replace("+", "").replace(" ", "")

# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

# --- Google Sheets ---
SHEET_ID = os.getenv("SHEET_ID", "")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")

# --- Local storage (chat memory, half-finished bookings, handoff flags) ---
DB_PATH = os.getenv("DB_PATH", "glow.db")

# --- The salon (identical every day) ---
SALON_NAME = "Glow Studio"
SALON_ADDRESS = "12 MG Road, Bengaluru"
TIMEZONE = "Asia/Kolkata"
OPEN_HOUR = 10   # 10 AM
CLOSE_HOUR = 19  # 7 PM -> last 1-hour slot starts at 6 PM
DAYS_AHEAD = 7
