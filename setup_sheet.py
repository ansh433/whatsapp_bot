"""One-time setup: creates the Services and Bookings tabs in your Google Sheet and fills in the services.

Run once after putting SHEET_ID and the service-account key in place:
    python setup_sheet.py
"""
import sheets

# (id, name, price in rupees). Edit these in the sheet itself any time afterwards.
SERVICES = [
    ("haircut", "Haircut", 400),
    ("hair-spa", "Hair Spa", 900),
    ("facial", "Facial", 1200),
    ("manicure", "Manicure", 600),
    ("hair-colour", "Hair Colour", 1800),
]

if __name__ == "__main__":
    sheets.init_sheet(SERVICES)
    print("Done. The sheet now has Services and Bookings tabs.")
