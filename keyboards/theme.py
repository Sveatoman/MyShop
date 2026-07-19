"""Стили кнопок Telegram (Bot API 9.4).

Настоящего золотого цвета нет — только primary / success / danger.
Для Funeral Shop: основные действия — primary (акцент),
оплата/подтверждение — success, удаление/отмена — danger.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional

DANGER_CALLBACK_PREFIXES = (
    "adm_delserv_",
    "adm_catdel_",
    "admin_delpromo_",
    "admin_close_ticket_",
)
SUCCESS_CALLBACKS = {
    "pay_now",
    "adm_upload_done",
    "adm_edit_upload_done",
    "admin_broadcast_confirm",
    "admin_create_promo",
    "admin_create_category",
    "top_up_balance",
    "activate_promo",
}
SUCCESS_CALLBACK_PREFIXES = (
    "pay_crypto",
    "pay_rocket",
    "check_crypto_",
    "check_rocket_",
)

DANGER_TEXT = (
    "удал",
    "отмен",
    "отменить",
    "закрыть без",
)
SUCCESS_TEXT = (
    "оплат",
    "подтверд",
    "заверш",
    "создать",
    "пополн",
)


def _resolve_style(text: str, callback_data: str) -> str:
    lower = text.lower()

    if any(callback_data.startswith(p) for p in DANGER_CALLBACK_PREFIXES):
        return "danger"
    if any(m in lower for m in DANGER_TEXT):
        return "danger"

    if callback_data in SUCCESS_CALLBACKS:
        return "success"
    if any(callback_data.startswith(p) for p in SUCCESS_CALLBACK_PREFIXES):
        return "success"
    if any(m in lower for m in SUCCESS_TEXT):
        return "success"

    return "primary"


def themed(markup: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Накладывает цветовые стили на inline-клавиатуру."""
    if not markup or "inline_keyboard" not in markup:
        return markup

    result = copy.deepcopy(markup)
    for row in result["inline_keyboard"]:
        for btn in row:
            if not isinstance(btn, dict):
                continue
            if btn.get("style"):
                continue

            text = btn.get("text") or ""
            callback_data = btn.get("callback_data") or ""
            btn["style"] = _resolve_style(text, callback_data)

    return result
