import datetime
from typing import List, Dict, Any

from keyboards.theme import themed

def get_main_menu() -> dict:
    """Генерирует инлайн-клавиатуру главного меню пользователя."""
    return themed({
        "inline_keyboard": [
            [
                {"text": "Каталог", "callback_data": "catalog", "icon_custom_emoji_id": "5877485980901971030"},
                {"text": "Наличие товаров", "callback_data": "check_stock", "icon_custom_emoji_id": "5967456680940671207"}
            ],
            [
                {"text": "Профиль", "callback_data": "user_profile", "icon_custom_emoji_id": "5316727448644103237"},
                {"text": "Поддержка", "callback_data": "user_support", "icon_custom_emoji_id": "5988023995125993550"}
            ],
            [
                {"text": "Политика конфиденциальности", "callback_data": "privacy_policy"},
                {"text": "Соглашение", "callback_data": "user_agreement"}
            ]
        ]
    })

def get_catalog_categories_keyboard(
    categories: List[Dict[str, Any]],
    category_counts: Dict[int, int],
    uncategorized_count: int = 0
) -> dict:
    """Клавиатура категорий каталога для пользователя."""
    keyboard = []
    for category in categories:
        count = category_counts.get(category["id"], 0)
        if count <= 0:
            continue
        keyboard.append([{
            "text": f"{category['name']} ({count})",
            "callback_data": f"catalog_cat_{category['id']}"
        }])
    if uncategorized_count > 0:
        keyboard.append([{
            "text": f"Без категории ({uncategorized_count})",
            "callback_data": "catalog_cat_none"
        }])
    keyboard.append([{
        "text": "Назад в меню",
        "callback_data": "user_to_menu",
        "icon_custom_emoji_id": "5877536313623711363"
    }])
    return themed({"inline_keyboard": keyboard})

def get_buy_services_keyboard(
    services: List[Dict[str, Any]],
    available_counts: Dict[int, int],
    back_callback: str = "catalog"
) -> dict:
    """Генерирует клавиатуру со списком сервисов и количеством аккаунтов."""
    keyboard = []
    for service in services:
        service_id = service["id"]
        count = available_counts.get(service_id, 0)
        if count <= 0:
            continue
        keyboard.append([{
            "text": f"{service['name']} ({count})",
            "callback_data": f"buy_serv_{service_id}"
        }])
    keyboard.append([{
        "text": "Назад",
        "callback_data": back_callback,
        "icon_custom_emoji_id": "5877536313623711363"
    }])
    return themed({"inline_keyboard": keyboard})

def get_categories_keyboard(service_id: int, categories: Dict[str, Dict[str, Any]], back_callback: str = "catalog") -> dict:
    """
    Генерирует клавиатуру категорий отлёжки.
    Показываются только категории с количеством > 0.
    """
    keyboard = []
    for idx, (cat_name, info) in enumerate(categories.items()):
        count = len(info["accounts"])
        if count <= 0:
            continue
        price = info["price"]
        display_name = "Свежие" if cat_name == "Свежие" else cat_name
        keyboard.append([{
            "text": f"{display_name} ({count} шт.) - ${price:.2f}",
            "callback_data": f"buy_cat_{idx}"
        }])
    keyboard.append([{
        "text": "К списку товаров",
        "callback_data": back_callback,
        "icon_custom_emoji_id": "5877536313623711363"
    }])
    return themed({"inline_keyboard": keyboard})

def get_payment_keyboard() -> dict:
    """Генерирует инлайн-клавиатуру с кнопкой оплаты."""
    return themed({
        "inline_keyboard": [
            [{"text": "Оплатить", "callback_data": "pay_now", "icon_custom_emoji_id": "5967390100357648692"}],
            [{"text": "Отменить покупку", "callback_data": "user_to_menu", "icon_custom_emoji_id": "5778527486270770928"}]
        ]
    })

def get_history_keyboard(orders: List[Dict[str, Any]]) -> dict:
    """Генерирует клавиатуру со списком последних покупок (до 10 шт)."""
    keyboard = []
    for order in orders:
        date_str = datetime.datetime.fromtimestamp(order["purchased_at"]).strftime("%d.%m")
        btn_text = f"{order['service_name']} [{order['category']}] ({order['quantity']} шт.) - {date_str}"
        keyboard.append([{
            "text": btn_text,
            "callback_data": f"show_ord_{order['id']}"
        }])
    keyboard.append([{
        "text": "Назад в профиль",
        "callback_data": "user_profile",
        "icon_custom_emoji_id": "5877536313623711363"
    }])
    return themed({"inline_keyboard": keyboard})

def get_profile_kb() -> dict:
    """Генерирует клавиатуру для профиля пользователя."""
    return themed({
        "inline_keyboard": [
            [{"text": "Пополнить баланс", "callback_data": "top_up_balance", "icon_custom_emoji_id": "5258204546391351475"}],
            [{"text": "Активировать промокод", "callback_data": "activate_promo", "icon_custom_emoji_id": "5967390100357648692"}],
            [{"text": "История покупок", "callback_data": "history_purchases", "icon_custom_emoji_id": "5875206779196935950"}],
            [{"text": "Назад в меню", "callback_data": "user_to_menu", "icon_custom_emoji_id": "5877536313623711363"}]
        ]
    })

def get_payment_systems_kb() -> dict:
    """Генерирует клавиатуру платежных систем."""
    return themed({
        "inline_keyboard": [
            [{"text": "🤖 CryptoBot", "callback_data": "pay_cryptobot"}],
            [{"text": "🚀 xRocket", "callback_data": "pay_xrocket"}],
            [{"text": "Назад в профиль", "callback_data": "user_profile", "icon_custom_emoji_id": "5877536313623711363"}]
        ]
    })
