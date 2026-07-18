import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x}
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
XROCKET_TOKEN = os.getenv("XROCKET_TOKEN")

PRICE_INCREMENT_PER_12H = 0
