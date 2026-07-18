from typing import List, Dict, Any

def get_admin_menu(open_tickets_count: int = 0) -> dict:
    """Генерирует инлайн-клавиатуру главного меню администратора."""
    tickets_btn_text = f"Обращения ({open_tickets_count})" if open_tickets_count > 0 else "Обращения"
    return {
        "inline_keyboard": [
            [
                {"text": "Обновить", "callback_data": "admin_refresh", "icon_custom_emoji_id": "5823396554345549784"}
            ],
            [
                {"text": "Добавить товар", "callback_data": "admin_add_account", "icon_custom_emoji_id": "5967456680940671207"},
                {"text": "Редактировать", "callback_data": "admin_edit_services", "icon_custom_emoji_id": "5879841310902324730"}
            ],
            [
                {"text": "Промокоды", "callback_data": "admin_promos", "icon_custom_emoji_id": "5879841310902324730"},
                {"text": "Инфо Юзера", "callback_data": "admin_user_info", "icon_custom_emoji_id": "5920344347152224466"}
            ],
            [
                {"text": tickets_btn_text, "callback_data": "admin_tickets_list", "icon_custom_emoji_id": "5988023995125993550"}
            ],
            [
                {"text": "Рассылка", "callback_data": "admin_broadcast", "icon_custom_emoji_id": "5988023995125993550"}
            ],
            [
                {"text": "Состарить (+12ч)", "callback_data": "admin_age_accounts", "icon_custom_emoji_id": "5823396554345549784"}
            ]
        ]
    }

def get_services_keyboard(services: List[Dict[str, Any]], prefix: str = "adm_serv_") -> dict:
    """Генерирует клавиатуру со списком сервисов."""
    keyboard = []
    for service in services:
        keyboard.append([{
            "text": f"{service['name']} (${service['base_price']:.2f})",
            "callback_data": f"{prefix}{service['id']}"
        }])
    keyboard.append([{
        "text": "Назад в меню",
        "callback_data": "admin_to_menu",
        "icon_custom_emoji_id": "5877536313623711363"
    }])
    return {"inline_keyboard": keyboard}

def get_service_edit_menu(service_id: int) -> dict:
    """Генерирует меню действий редактирования сервиса."""
    return {
        "inline_keyboard": [
            [{"text": "Изменить цену", "callback_data": f"adm_editprice_{service_id}", "icon_custom_emoji_id": "5778318458802409852"}],
            [{"text": "Догрузить аккаунты", "callback_data": f"adm_upload_{service_id}", "icon_custom_emoji_id": "5967456680940671207"}],
            [{"text": "Удалить сервис", "callback_data": f"adm_delserv_{service_id}", "icon_custom_emoji_id": "5778527486270770928"}],
            [{"text": "К списку сервисов", "callback_data": "admin_edit_services", "icon_custom_emoji_id": "5877536313623711363"}]
        ]
    }
