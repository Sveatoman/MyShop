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
    "Подписки",
    "Программное обеспечение",
    "Цифровые услуги",
]

SERVICES = [
    {
        "name": "Подписка Premium 1 месяц",
        "base_price": 2.99,
        "type": "text",
        "category": "Подписки",
        "description": (
            "⭐ <b>Что входит в товар:</b>\n"
            "• Активационный ключ подписки Premium на 1 месяц\n"
            "• Формат: <code>ключ активации</code>\n"
            "• Неограниченный доступ ко всем функциям платформы\n"
            "• Поддержка при активации в течение 24 часов"
        ),
        "accounts": [
            "PREM-1M-AAAA-1111",
            "PREM-1M-BBBB-2222",
            "PREM-1M-CCCC-3333",
            "PREM-1M-DDDD-4444",
            "PREM-1M-EEEE-5555",
        ],
    },
    {
        "name": "Подписка Premium 3 месяца",
        "base_price": 7.99,
        "type": "text",
        "category": "Подписки",
        "description": (
            "⭐ <b>Что входит в товар:</b>\n"
            "• Активационный ключ подписки Premium на 3 месяца\n"
            "• Формат: <code>ключ активации</code>\n"
            "• Полный доступ ко всем функциям на 90 дней\n"
            "• Поддержка при активации в течение 24 часов"
        ),
        "accounts": [
            "PREM-3M-AAAA-1111",
            "PREM-3M-BBBB-2222",
            "PREM-3M-CCCC-3333",
            "PREM-3M-DDDD-4444",
            "PREM-3M-EEEE-5555",
        ],
    },
    {
        "name": "Лицензия Software Basic",
        "base_price": 4.50,
        "type": "text",
        "category": "Программное обеспечение",
        "description": (
            "💻 <b>Что входит в товар:</b>\n"
            "• Лицензионный ключ активации программного обеспечения (Basic)\n"
            "• Формат: <code>серийный номер</code>\n"
            "• Лицензия на 1 устройство, бессрочная\n"
            "• Инструкция по активации прилагается"
        ),
        "accounts": [
            "SW-BASIC-XXXX-1111-AAAA",
            "SW-BASIC-XXXX-2222-BBBB",
            "SW-BASIC-XXXX-3333-CCCC",
            "SW-BASIC-XXXX-4444-DDDD",
            "SW-BASIC-XXXX-5555-EEEE",
        ],
    },
    {
        "name": "Лицензия Software Pro",
        "base_price": 9.99,
        "type": "text",
        "category": "Программное обеспечение",
        "description": (
            "💻 <b>Что входит в товар:</b>\n"
            "• Лицензионный ключ активации программного обеспечения (Pro)\n"
            "• Формат: <code>серийный номер</code>\n"
            "• Лицензия на 3 устройства, бессрочная\n"
            "• Расширенный функционал и приоритетная поддержка"
        ),
        "accounts": [
            "SW-PRO-XXXX-1111-AAAA",
            "SW-PRO-XXXX-2222-BBBB",
            "SW-PRO-XXXX-3333-CCCC",
            "SW-PRO-XXXX-4444-DDDD",
            "SW-PRO-XXXX-5555-EEEE",
        ],
    },
    {
        "name": "Пакет цифровых услуг Starter",
        "base_price": 1.99,
        "type": "text",
        "category": "Цифровые услуги",
        "description": (
            "🎁 <b>Что входит в товар:</b>\n"
            "• Доступ к пакету цифровых услуг уровня Starter\n"
            "• Формат: <code>логин:пароль</code>\n"
            "• Включает базовый набор инструментов и сервисов\n"
            "• Техническая поддержка и замена при сбое в течение 24 часов"
        ),
        "accounts": [
            "starter_001:StPass#001",
            "starter_002:StPass#002",
            "starter_003:StPass#003",
            "starter_004:StPass#004",
            "starter_005:StPass#005",
        ],
    },
    {
        "name": "Пакет цифровых услуг Business",
        "base_price": 14.99,
        "type": "text",
        "category": "Цифровые услуги",
        "description": (
            "🏢 <b>Что входит в товар:</b>\n"
            "• Доступ к пакету цифровых услуг уровня Business\n"
            "• Формат: <code>логин:пароль</code>\n"
            "• Расширенный функционал для бизнес-задач\n"
            "• Приоритетная поддержка и гарантия замены 48 часов"
        ),
        "accounts": [
            "business_001:BizPass#001",
            "business_002:BizPass#002",
            "business_003:BizPass#003",
            "business_004:BizPass#004",
            "business_005:BizPass#005",
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
