import aiohttp
import logging
from config import CRYPTOBOT_TOKEN, XROCKET_TOKEN

logger = logging.getLogger(__name__)

class PaymentService:

    @staticmethod
    async def create_cryptobot_invoice(amount_usd: float, user_id: int):
        """Создание счета в CryptoBot в USDT (MAINNET / БОЕВАЯ СЕTЬ)"""
        url = "https://pay.crypt.bot/api/createInvoice"

        headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}

        payload = {
            "currency_type": "crypto",
            "asset": "USDT",
            "amount": str(round(amount_usd, 2)),
            "description": "Пополнение баланса в Bot Shop",
            "payload": f"topup_{user_id}_{amount_usd}"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=payload) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        res = data["result"]
                        return {
                            "invoice_id": str(res["invoice_id"]),
                            "pay_url": res["bot_invoice_url"],
                            "amount_usd": amount_usd
                        }
                    else:
                        logger.error(f"CryptoBot Mainnet API error: {data}")
            except Exception as e:
                logger.error(f"CryptoBot Mainnet create error: {e}")
        return None

    @staticmethod
    async def check_cryptobot_invoice(invoice_id: str):
        """Проверка статуса инвойса CryptoBot (MAINNET / БОЕВАЯ СЕТЬ)"""
        url = "https://pay.crypt.bot/api/getInvoices"

        headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
        params = {"invoice_ids": invoice_id}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                    if data.get("ok") and data["result"]["items"]:
                        invoice = data["result"]["items"][0]
                        return invoice["status"] == "paid"
            except Exception as e:
                logger.error(f"CryptoBot check error: {e}")
        return False

    @staticmethod
    async def create_xrocket_invoice(amount_usd: float, user_id: int):
        """Создание счета в xRocket (в USDT)"""
        url = "https://pay.xrocket.exchange/tg-invoices"
        headers = {"Rocket-Pay-Key": XROCKET_TOKEN}

        payload = {
            "amount": round(amount_usd, 2),
            "currency": "USDT",
            "description": "Пополнение баланса в Bot Shop",
            "payload": f"topup_{user_id}_{amount_usd}",
            "expiredIn": 1800
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=payload) as resp:
                    data = await resp.json()
                    if data.get("success"):
                        res = data["data"]
                        return {
                            "invoice_id": str(res["id"]),
                            "pay_url": res["link"],
                            "amount_usd": amount_usd
                        }
            except Exception as e:
                logger.error(f"xRocket create error: {e}")
        return None

    @staticmethod
    async def check_xrocket_invoice(invoice_id: str):
        """Проверка статуса инвойса xRocket"""
        url = f"https://pay.xrocket.exchange/tg-invoices/{invoice_id}"
        headers = {"Rocket-Pay-Key": XROCKET_TOKEN}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers) as resp:
                    data = await resp.json()
                    if data.get("success"):
                        return data["data"]["status"] == "paid"
            except Exception as e:
                logger.error(f"xRocket check error: {e}")
        return False
