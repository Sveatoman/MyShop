"""
Скрипт засева демо-товарами для демонстрации банку.
Запуск: python seed_demo.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database

CATEGORIES = [
    "AI-сервисы",
    "VPN и безопасность",
    "Облачные хранилища",
]

SERVICES = [
    {
        "name": "Google Gemini Pro — 18 месяцев",
        "base_price": 29.99,
        "type": "text",
        "category": "AI-сервисы",
        "description": (
            "🤖 <b>Google Gemini Pro — подписка 18 месяцев</b>\n"
            "• Активационный код для Google Gemini Advanced\n"
            "• Формат: <code>код активации</code>\n"
            "• Полный доступ к Gemini Pro, 1 ТБ в Google One\n"
            "• Привязка к вашему Google-аккаунту, поддержка 24 ч"
        ),
        "accounts": [
            "GEM-PRO-18M-7FK2-XNRA",
            "GEM-PRO-18M-9PL4-BVTC",
            "GEM-PRO-18M-3QW8-DMEY",
            "GEM-PRO-18M-6HJ1-KSGF",
            "GEM-PRO-18M-2UT5-WNPZ",
        ],
    },
    {
        "name": "ChatGPT Plus — 12 месяцев",
        "base_price": 49.99,
        "type": "text",
        "category": "AI-сервисы",
        "description": (
            "🤖 <b>ChatGPT Plus — подписка 12 месяцев</b>\n"
            "• Код активации подписки ChatGPT Plus (OpenAI)\n"
            "• Формат: <code>код активации</code>\n"
            "• GPT-4o, приоритетный доступ, DALL·E, Advanced Data Analysis\n"
            "• Мгновенная доставка, поддержка при активации"
        ),
        "accounts": [
            "CGPT-PLUS-12M-AX4R-9FKD",
            "CGPT-PLUS-12M-BN7T-3HWQ",
            "CGPT-PLUS-12M-CP2M-6JVL",
            "CGPT-PLUS-12M-DK8S-1YNB",
            "CGPT-PLUS-12M-EW5G-4ZPC",
        ],
    },
    {
        "name": "NordVPN — 24 месяца",
        "base_price": 19.99,
        "type": "text",
        "category": "VPN и безопасность",
        "description": (
            "🔒 <b>NordVPN — подписка 24 месяца</b>\n"
            "• Лицензионный ключ NordVPN на 2 года\n"
            "• Формат: <code>ключ активации</code>\n"
            "• 6 устройств одновременно, 5800+ серверов\n"
            "• Threat Protection, Kill Switch, без логов"
        ),
        "accounts": [
            "NORD-24M-KF82-QXVW-A1",
            "NORD-24M-PL37-TNRB-B2",
            "NORD-24M-WS94-HCJD-C3",
            "NORD-24M-MX61-YGKE-D4",
            "NORD-24M-BV45-ZUFP-E5",
        ],
    },
    {
        "name": "Surfshark VPN — 12 месяцев",
        "base_price": 12.99,
        "type": "text",
        "category": "VPN и безопасность",
        "description": (
            "🔒 <b>Surfshark VPN — подписка 12 месяцев</b>\n"
            "• Код активации Surfshark на 1 год\n"
            "• Формат: <code>код активации</code>\n"
            "• Безлимит устройств, CleanWeb, MultiHop\n"
            "• 3200+ серверов в 100 странах"
        ),
        "accounts": [
            "SHARK-12M-QN84-FXWT-01",
            "SHARK-12M-RK27-GVML-02",
            "SHARK-12M-TJ53-HPDS-03",
            "SHARK-12M-UW96-YBCN-04",
            "SHARK-12M-XE41-ZARQ-05",
        ],
    },
    {
        "name": "Google One 2 ТБ — 12 месяцев",
        "base_price": 17.99,
        "type": "text",
        "category": "Облачные хранилища",
        "description": (
            "☁️ <b>Google One 2 ТБ — подписка 12 месяцев</b>\n"
            "• Код активации Google One (2 ТБ хранилища)\n"
            "• Формат: <code>код активации</code>\n"
            "• Google Drive, Gmail, Google Photos — общее пространство\n"
            "• Семейный доступ до 5 участников"
        ),
        "accounts": [
            "GONE-2TB-12M-AF73-NXQK",
            "GONE-2TB-12M-BH29-PWRL",
            "GONE-2TB-12M-CJ85-SVTM",
            "GONE-2TB-12M-DM41-UXWN",
            "GONE-2TB-12M-EQ67-ZYAP",
        ],
    },
    {
        "name": "iCloud+ 200 ГБ — 6 месяцев",
        "base_price": 8.99,
        "type": "text",
        "category": "Облачные хранилища",
        "description": (
            "☁️ <b>iCloud+ 200 ГБ — подписка 6 месяцев</b>\n"
            "• Подарочный код iCloud+ (200 ГБ) на 6 месяцев\n"
            "• Формат: <code>код погашения</code>\n"
            "• Private Relay, Hide My Email, HomeKit Secure Video\n"
            "• Активация через Apple ID"
        ),
        "accounts": [
            "ICLD-200G-6M-XKR4-92TF",
            "ICLD-200G-6M-YNW7-83QG",
            "ICLD-200G-6M-ZPV1-65MH",
            "ICLD-200G-6M-AQS8-47DJ",
            "ICLD-200G-6M-BTU3-18CK",
        ],
    },
]


async def main():
    await database.init_db()
    print("БД инициализирована.")

    cat_map = {}
    for cat_name in CATEGORIES:
        existing = await database.get_all_categories()
        found = next((c for c in existing if c["name"] == cat_name), None)
        if found:
            cat_map[cat_name] = found["id"]
            print(f"Категория '{cat_name}' уже существует (id={found['id']}).")
        else:
            cat_id = await database.create_category(cat_name)
            cat_map[cat_name] = cat_id
            print(f"Создана категория '{cat_name}' (id={cat_id}).")

    for svc in SERVICES:
        existing = await database.get_service_by_name(svc["name"])
        if existing:
            print(f"Сервис '{svc['name']}' уже существует, пропускаем.")
            continue
        cat_id = cat_map.get(svc["category"])
        svc_id = await database.create_service(
            name=svc["name"],
            base_price=svc["base_price"],
            service_type=svc["type"],
            category_id=cat_id,
            description=svc["description"],
        )
        await database.add_accounts(svc_id, svc["accounts"])
        print(f"Создан сервис '{svc['name']}' с {len(svc['accounts'])} аккаунтами.")

    print("\nГотово! Все демо-товары загружены.")


if __name__ == "__main__":
    asyncio.run(main())
