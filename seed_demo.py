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
    "Социальные сети",
    "Мессенджеры",
    "E-commerce",
]

SERVICES = [
    {
        "name": "Аккаунты Instagram",
        "base_price": 1.50,
        "type": "text",
        "category": "Социальные сети",
        "description": (
            "📱 <b>Что входит в товар:</b>\n"
            "• Готовый аккаунт Instagram с заполненным профилем\n"
            "• Формат: <code>логин:пароль:почта:пароль_почты</code>\n"
            "• Аккаунты прошли верификацию, не имеют ограничений\n"
            "• Гарантия замены в течение 24 часов при техническом сбое"
        ),
        "accounts": [
            "user_insta1:Pass@1234:mail1@gmail.com:MailPass1",
            "user_insta2:Pass@5678:mail2@gmail.com:MailPass2",
            "user_insta3:Pass@9012:mail3@gmail.com:MailPass3",
            "user_insta4:Pass@3456:mail4@gmail.com:MailPass4",
            "user_insta5:Pass@7890:mail5@gmail.com:MailPass5",
        ],
    },
    {
        "name": "Аккаунты TikTok",
        "base_price": 2.00,
        "type": "text",
        "category": "Социальные сети",
        "description": (
            "🎵 <b>Что входит в товар:</b>\n"
            "• Готовый аккаунт TikTok с историей активности\n"
            "• Формат: <code>логин:пароль</code>\n"
            "• Аккаунты не забанены, прошли проверку на работоспособность\n"
            "• Замена при невозможности входа в течение 24 часов"
        ),
        "accounts": [
            "tiktok_user1:TkPass@111",
            "tiktok_user2:TkPass@222",
            "tiktok_user3:TkPass@333",
            "tiktok_user4:TkPass@444",
            "tiktok_user5:TkPass@555",
        ],
    },
    {
        "name": "Аккаунты Telegram",
        "base_price": 3.50,
        "type": "text",
        "category": "Мессенджеры",
        "description": (
            "💬 <b>Что входит в товар:</b>\n"
            "• Аккаунт Telegram, зарегистрированный на реальный номер\n"
            "• Формат: <code>номер:API_ID:API_HASH:session_string</code>\n"
            "• Аккаунт не имеет ограничений SpamBlock\n"
            "• Поддержка 24/7 при возникновении вопросов"
        ),
        "accounts": [
            "+79001234001:12345:abcdefgh:session_str_001",
            "+79001234002:12346:abcdefgi:session_str_002",
            "+79001234003:12347:abcdefgj:session_str_003",
            "+79001234004:12348:abcdefgk:session_str_004",
            "+79001234005:12349:abcdefgl:session_str_005",
        ],
    },
    {
        "name": "Аккаунты WhatsApp",
        "base_price": 2.50,
        "type": "text",
        "category": "Мессенджеры",
        "description": (
            "📞 <b>Что входит в товар:</b>\n"
            "• Готовый аккаунт WhatsApp с привязкой к номеру\n"
            "• Формат: <code>номер:пароль_резервной_копии</code>\n"
            "• Аккаунты без блокировок, готовы к использованию\n"
            "• Гарантия работоспособности 24 часа"
        ),
        "accounts": [
            "+79002345001:WaPass#001",
            "+79002345002:WaPass#002",
            "+79002345003:WaPass#003",
            "+79002345004:WaPass#004",
            "+79002345005:WaPass#005",
        ],
    },
    {
        "name": "Аккаунты Amazon",
        "base_price": 5.00,
        "type": "text",
        "category": "E-commerce",
        "description": (
            "🛒 <b>Что входит в товар:</b>\n"
            "• Аккаунт Amazon с историей покупок\n"
            "• Формат: <code>email:пароль</code>\n"
            "• Аккаунты зарегистрированы на реальные данные\n"
            "• Привязана платёжная карта (проверена на работоспособность)"
        ),
        "accounts": [
            "buyer_amz1@gmail.com:AmzPass@001",
            "buyer_amz2@gmail.com:AmzPass@002",
            "buyer_amz3@gmail.com:AmzPass@003",
            "buyer_amz4@gmail.com:AmzPass@004",
            "buyer_amz5@gmail.com:AmzPass@005",
        ],
    },
    {
        "name": "Аккаунты eBay",
        "base_price": 4.00,
        "type": "text",
        "category": "E-commerce",
        "description": (
            "📦 <b>Что входит в товар:</b>\n"
            "• Аккаунт eBay с подтверждённым email\n"
            "• Формат: <code>email:пароль</code>\n"
            "• Рейтинг покупателя от 10 отзывов\n"
            "• Поддержка и замена при проблемах в течение 24 часов"
        ),
        "accounts": [
            "ebay_buyer1@mail.com:EbayPass@001",
            "ebay_buyer2@mail.com:EbayPass@002",
            "ebay_buyer3@mail.com:EbayPass@003",
            "ebay_buyer4@mail.com:EbayPass@004",
            "ebay_buyer5@mail.com:EbayPass@005",
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
