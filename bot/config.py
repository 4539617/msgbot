import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()
]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env")

if not ADMIN_IDS:
    raise ValueError("ADMIN_IDS is not set in .env")
