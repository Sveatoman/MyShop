import asyncio
import logging
import aiosqlite
from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config import ADMIN_IDS
import database
from keyboards.admin_kb import (
    get_admin_menu,
    get_services_keyboard,
    get_service_edit_menu,
    get_categories_manage_keyboard,
    get_category_edit_menu,
    get_category_pick_keyboard,
)
from keyboards.theme import themed
from services.custom_methods import SendCustomMessage, SendCustomPhoto, EditCustomMessageText, EditCustomMessageMedia

logger = logging.getLogger(__name__)

upload_buffers = {}

async def send_upload_summary_after_delay(message: Message, state: FSMContext, user_id: int, delay: float = 1.5):
    try:
        await asyncio.sleep(delay)
        buffer = upload_buffers.pop(user_id, None)
        if not buffer:
            return

        files = buffer["files"]
        service_id = buffer["service_id"]
        service_name = buffer["service_name"]
        is_edit = buffer["is_edit"]

        total_in_db = await database.get_available_accounts_count(service_id)
        count_uploaded = len(files)

        if count_uploaded <= 5:
            files_list = "\n".join([f"• <code>{f}</code>" for f in files])
        else:
            files_list = "\n".join([f"• <code>{f}</code>" for f in files[:5]]) + f"\n... и еще {count_uploaded - 5} файлов."

        if is_edit:
            done_kb = {
                "inline_keyboard": [
                    [{"text": "Завершить загрузку", "callback_data": "adm_edit_upload_done", "icon_custom_emoji_id": "5951665890079544884"}],
                    [{"text": "Отмена", "callback_data": f"adm_serv_{service_id}", "icon_custom_emoji_id": "5778527486270770928"}]
                ]
            }
        else:
            done_kb = {
                "inline_keyboard": [
                    [{"text": "Завершить загрузку", "callback_data": "adm_upload_done", "icon_custom_emoji_id": "5951665890079544884"}],
                    [{"text": "Отмена", "callback_data": "admin_to_menu", "icon_custom_emoji_id": "5778527486270770928"}]
                ]
            }

        text = (
            f"<b><tg-emoji emoji-id=\"5967456680940671207\">📥</tg-emoji> Успешно загружено файлов в этой сессии: {count_uploaded} шт.</b>\n"
            f"{files_list}\n\n"
            f"<b><tg-emoji emoji-id=\"5967456680940671207\">📦</tg-emoji> Всего доступно файлов в {service_name}:</b> {total_in_db} шт.\n\n"
            f"Пришли еще файлы или нажми кнопку ниже для завершения:"
        )

        await message.answer(text, reply_markup=themed(done_kb), parse_mode="HTML")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error sending upload summary: {e}")

router = Router()

IMG_ADMIN = "https://i.ibb.co/yBhjvr7V/image.png"

class AdminAddAccount(StatesGroup):
    waiting_for_type = State()
    waiting_for_category = State()
    waiting_for_service_name = State()
    waiting_for_base_price = State()
    waiting_for_credentials = State()

class AdminEditService(StatesGroup):
    waiting_for_new_price = State()
    waiting_for_new_credentials = State()

class AdminCategory(StatesGroup):
    waiting_for_name = State()
    waiting_for_rename = State()

class AdminPromo(StatesGroup):
    waiting_for_promo_data = State()

class AdminUserInfoState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_balance_change = State()

class AdminBroadcast(StatesGroup):
    waiting_for_broadcast_content = State()
    waiting_for_broadcast_confirm = State()

class AdminReplyState(StatesGroup):
    waiting_for_reply = State()

async def send_admin_panel(target, stats: dict, edit: bool = False):
    """Вспомогательная функция для генерации текста админ-панели."""
    text = (
        '<b><tg-emoji emoji-id="5877485980901971030">📊</tg-emoji> Панель администратора</b>\n\n'
        '<b>Пользователи:</b>\n'
        f'├ <tg-emoji emoji-id="5920344347152224466">👥</tg-emoji> <b>Всего пользователей:</b> <code>{stats["users_count"]}</code> <b>чел.</b>\n'
        f'╰ <tg-emoji emoji-id="5778318458802409852">💰</tg-emoji> <b>Баланс пользователей:</b> <code>${stats["total_balance"]:.2f}</code>\n\n'
        '<b>Продажи:</b>\n'
        f'├ <tg-emoji emoji-id="5985493993100679671">🛒</tg-emoji> <b>За сегодня:</b> <code>{stats.get("today_sold_count", 0)}</code> <b>шт.</b> (<code>${stats.get("today_sold_amount", 0.0):.2f}</code>)\n'
        f'├ <tg-emoji emoji-id="5967390100357648692">💵</tg-emoji> <b>За вчера:</b> <code>{stats.get("yesterday_sold_count", 0)}</code> <b>шт.</b> (<code>${stats.get("yesterday_sold_amount", 0.0):.2f}</code>)\n'
        f'├ <tg-emoji emoji-id="5877485980901971030">📊</tg-emoji> <b>За 30 дней:</b> <code>{stats.get("month_sold_count", 0)}</code> <b>шт.</b> (<code>${stats.get("month_sold_amount", 0.0):.2f}</code>)\n'
        f'╰ <tg-emoji emoji-id="5967456680940671207">📦</tg-emoji> <b>Всего:</b> <code>{stats["sold_count"]}</code> <b>шт.</b> (<code>${stats["sold_amount"]:.2f}</code>)\n\n'
        '<b>Магазин:</b>\n'
        f'├ <tg-emoji emoji-id="5967456680940671207">📦</tg-emoji> <b>Товаров в наличии:</b> <code>{stats["available_count"]}</code> <b>шт.</b>\n'
        f'├ <tg-emoji emoji-id="5879841310902324730">🎟</tg-emoji> <b>Активных промокодов:</b> <code>{stats.get("active_promos_count", 0)}</code> <b>шт.</b>\n'
        f'╰ <tg-emoji emoji-id="5988023995125993550">💬</tg-emoji> <b>Неотвеченных обращений:</b> <code>{stats.get("open_tickets_count", 0)}</code> <b>шт.</b>'
    )

    open_tickets = stats.get("open_tickets_count", 0)

    if edit:
        has_media = hasattr(target, "photo") and target.photo
        if has_media:
            try:
                await target.bot(EditCustomMessageMedia(
                    chat_id=target.chat.id,
                    message_id=target.message_id,
                    media={"type": "photo", "media": IMG_ADMIN, "caption": text, "parse_mode": "HTML"},
                    reply_markup=get_admin_menu(open_tickets)
                ))
                return
            except Exception:
                pass

        try:
            await target.delete()
        except Exception:
            pass
        await target.bot(SendCustomPhoto(
            chat_id=target.chat.id,
            photo=IMG_ADMIN,
            caption=text,
            parse_mode="HTML",
            reply_markup=get_admin_menu(open_tickets)
        ))
    else:
        await target.bot(SendCustomPhoto(
            chat_id=target.chat.id,
            photo=IMG_ADMIN,
            caption=text,
            parse_mode="HTML",
            reply_markup=get_admin_menu(open_tickets)
        ))

@router.message(Command("admin"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_admin(message: Message, state: FSMContext):
    """Показ админ-панели."""
    await state.clear()
    stats = await database.get_stats()
    await send_admin_panel(message, stats)

@router.callback_query(F.data == "admin_to_menu", F.from_user.id.in_(ADMIN_IDS))
async def callback_admin_to_menu(callback: CallbackQuery, state: FSMContext):
    """Кнопка возврата в меню."""
    await state.clear()
    stats = await database.get_stats()
    await send_admin_panel(callback.message, stats, edit=True)
    await callback.answer()

@router.callback_query(F.data == "admin_refresh", F.from_user.id.in_(ADMIN_IDS))
async def process_admin_refresh(callback: CallbackQuery):
    """Обновление статистики."""
    stats = await database.get_stats()
    try:
        await send_admin_panel(callback.message, stats, edit=True)
    except Exception:
        pass
    await callback.answer("Статистика обновлена")

@router.callback_query(F.data == "admin_age_accounts", F.from_user.id.in_(ADMIN_IDS))
async def process_admin_age_accounts(callback: CallbackQuery):
    """Искусственно состаривает все непроданные аккаунты на 12 часов для тестов."""
    await database.age_accounts_by_12_hours()
    stats = await database.get_stats()
    try:
        await send_admin_panel(callback.message, stats, edit=True)
    except Exception:
        pass
    await callback.answer("Все непроданные аккаунты состарены на 12 часов!", show_alert=True)

@router.callback_query(F.data == "admin_add_account", F.from_user.id.in_(ADMIN_IDS))
async def start_add_account(callback: CallbackQuery, state: FSMContext):
    """Шаг 1: Выбор типа товара."""
    await state.set_state(AdminAddAccount.waiting_for_type)
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Текстовые", "callback_data": "adm_addtype_text", "icon_custom_emoji_id": "5879841310902324730"},
                {"text": "Файлы", "callback_data": "adm_addtype_file", "icon_custom_emoji_id": "5875206779196935950"}
            ],
            [{"text": "Отмена", "callback_data": "admin_to_menu", "icon_custom_emoji_id": "5778527486270770928"}]
        ]
    }
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN, "caption": "<b><tg-emoji emoji-id=\"5877485980901971030\">⚙️</tg-emoji> Выбери тип добавляемого товара:</b>", "parse_mode": "HTML"},
        reply_markup=keyboard
    ))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_addtype_"), F.from_user.id.in_(ADMIN_IDS))
async def process_add_type(callback: CallbackQuery, state: FSMContext):
    """Шаг 2: Выбор категории каталога для товара."""
    service_type = callback.data.split("_")[2]
    await state.update_data(service_type=service_type)
    await state.set_state(AdminAddAccount.waiting_for_category)

    categories = await database.get_all_categories()
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_ADMIN,
            "caption": "<b><tg-emoji emoji-id=\"5967456680940671207\">📂</tg-emoji> Выбери категорию для товара:</b>",
            "parse_mode": "HTML"
        },
        reply_markup=get_category_pick_keyboard(categories, prefix="adm_addcat_", include_none=True)
    ))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_addcat_"), AdminAddAccount.waiting_for_category, F.from_user.id.in_(ADMIN_IDS))
async def process_add_category_pick(callback: CallbackQuery, state: FSMContext):
    """Шаг 3: Запрос названия сервиса после выбора категории."""
    raw_id = callback.data.replace("adm_addcat_", "", 1)
    if raw_id == "none":
        category_id = None
        category_name = "Без категории"
    else:
        category_id = int(raw_id)
        category = await database.get_category_by_id(category_id)
        if not category:
            await callback.answer("❌ Категория не найдена!", show_alert=True)
            return
        category_name = category["name"]

    await state.update_data(category_id=category_id, category_name=category_name)
    await state.set_state(AdminAddAccount.waiting_for_service_name)

    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отмена",
            "callback_data": "admin_to_menu",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_ADMIN,
            "caption": f"<b><tg-emoji emoji-id=\"5879841310902324730\">📝</tg-emoji> Категория: {category_name}</b>\n\n"
                       f"<b>Введи название сервиса (например: Carousell):</b>",
            "parse_mode": "HTML"
        },
        reply_markup=cancel_kb
    ))
    await callback.answer()

@router.message(AdminAddAccount.waiting_for_service_name, F.from_user.id.in_(ADMIN_IDS))
async def process_service_name(message: Message, state: FSMContext):
    """Обработка названия сервиса."""
    service_name = message.text.strip()
    if not service_name:
        await message.answer('<b><tg-emoji emoji-id="5778527486270770928">❌</tg-emoji> Название сервиса не может быть пустым. Введи название:</b>', parse_mode="HTML")
        return

    service = await database.get_service_by_name(service_name)
    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отмена",
            "callback_data": "admin_to_menu",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }

    if service:

        await state.update_data(service_id=service["id"], service_name=service["name"], service_type=service["type"])
        await state.set_state(AdminAddAccount.waiting_for_credentials)
        if service["type"] == "text":
            prompt = (
                f"<b><tg-emoji emoji-id=\"5920344347152224466\">ℹ️</tg-emoji> Сервис {service['name']} уже существует (базовая цена: ${service['base_price']:.2f}, тип: Текстовые).</b>\n\n"
                f"<b><tg-emoji emoji-id=\"5967456680940671207\">📥</tg-emoji> Пришли список аккаунтов (каждый аккаунт с новой строки в формате <code>логин:пароль</code>):</b>"
            )
        else:
            prompt = (
                f"<b><tg-emoji emoji-id=\"5920344347152224466\">ℹ️</tg-emoji> Сервис {service['name']} уже существует (цена: ${service['base_price']:.2f}, тип: Файлы).</b>\n\n"
                f"<b><tg-emoji emoji-id=\"5967456680940671207\">📥</tg-emoji> Отправь файлы (.json или .txt) одним или несколькими сообщениями:</b>"
            )
        await message.bot(SendCustomMessage(
            chat_id=message.chat.id,
            text=prompt,
            parse_mode="HTML",
            reply_markup=cancel_kb
        ))
    else:

        await state.update_data(service_name=service_name)
        await state.set_state(AdminAddAccount.waiting_for_base_price)
        await message.bot(SendCustomMessage(
            chat_id=message.chat.id,
            text=f"<b><tg-emoji emoji-id=\"5967456680940671207\">🆕</tg-emoji> Сервис {service_name} еще не создан.</b>\n\n"
                 f"<b><tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> Введи базовую цену за 1 шт. в $ (например, <code>1.50</code>):</b>",
            parse_mode="HTML",
            reply_markup=cancel_kb
        ))

@router.message(AdminAddAccount.waiting_for_base_price, F.from_user.id.in_(ADMIN_IDS))
async def process_base_price(message: Message, state: FSMContext):
    """Шаг 3: Ввод цены и создание сервиса."""
    try:
        price = float(message.text.replace(",", "."))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer('<b><tg-emoji emoji-id="5778527486270770928">❌</tg-emoji> Неверный формат цены. Введи положительное число (например: 1.50):</b>', parse_mode="HTML")
        return

    data = await state.get_data()
    service_name = data["service_name"]
    service_type = data["service_type"]
    category_id = data.get("category_id")

    service_id = await database.create_service(service_name, price, service_type, category_id=category_id)
    await state.update_data(service_id=service_id)

    await state.set_state(AdminAddAccount.waiting_for_credentials)
    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отмена",
            "callback_data": "admin_to_menu",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }

    if service_type == "text":
        prompt = f"<b><tg-emoji emoji-id=\"5951665890079544884\">✅</tg-emoji> Сервис {service_name} создан (тип: Текстовые, цена: ${price:.2f}).\n\n<tg-emoji emoji-id=\"5967456680940671207\">📥</tg-emoji> Пришли список аккаунтов (каждый аккаунт с новой строки в формате <code>логин:пароль</code>):</b>"
    else:
        prompt = f"<b><tg-emoji emoji-id=\"5951665890079544884\">✅</tg-emoji> Сервис {service_name} создан (тип: Файлы, цена: ${price:.2f}).\n\n<tg-emoji emoji-id=\"5967456680940671207\">📥</tg-emoji> Отправь файлы (.json или .txt) одним или несколькими сообщениями:</b>"

    await message.bot(SendCustomMessage(
        chat_id=message.chat.id,
        text=prompt,
        parse_mode="HTML",
        reply_markup=cancel_kb
    ))

@router.message(AdminAddAccount.waiting_for_credentials, F.text, F.from_user.id.in_(ADMIN_IDS))
async def process_credentials_text(message: Message, state: FSMContext):
    data = await state.get_data()
    service_type = data.get("service_type", "text")
    if service_type != "text":
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Этот сервис ожидает загрузку файлов (.json / .txt), а не текст!</b>", parse_mode="HTML")
        return

    text_data = message.text.strip()
    lines = [line.strip() for line in text_data.split("\n") if line.strip()]

    if not lines:
        await message.answer('<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Ты не прислал ни одной строки с аккаунтами. Попробуй еще раз:</b>', parse_mode="HTML")
        return

    service_id = data["service_id"]
    service_name = data["service_name"]

    await database.add_accounts(service_id, lines)
    await state.clear()

    stats = await database.get_stats()
    await message.answer(f"<b><tg-emoji emoji-id=\"5951665890079544884\">🎉</tg-emoji> Успешно загружено {len(lines)} шт. аккаунтов для сервиса {service_name}!</b>", parse_mode="HTML")
    await send_admin_panel(message, stats)

@router.message(AdminAddAccount.waiting_for_credentials, F.document, F.from_user.id.in_(ADMIN_IDS))
async def process_credentials_file(message: Message, state: FSMContext):
    data = await state.get_data()
    service_type = data.get("service_type", "text")
    if service_type != "file":
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Этот сервис ожидает загрузку текстовых аккаунтов, а не файлов!</b>", parse_mode="HTML")
        return

    file_name = message.document.file_name or ""
    if not (file_name.lower().endswith(".json") or file_name.lower().endswith(".txt")):
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Разрешены только файлы формата .json или .txt!</b>", parse_mode="HTML")
        return

    service_id = data["service_id"]
    service_name = data["service_name"]
    user_id = message.from_user.id

    await database.add_accounts(service_id, [message.document.file_id])

    if user_id not in upload_buffers:
        upload_buffers[user_id] = {
            "files": [],
            "task": None,
            "service_id": service_id,
            "service_name": service_name,
            "is_edit": False
        }

    upload_buffers[user_id]["files"].append(file_name)

    if upload_buffers[user_id]["task"]:
        upload_buffers[user_id]["task"].cancel()

    upload_buffers[user_id]["task"] = asyncio.create_task(
        send_upload_summary_after_delay(message, state, user_id, 1.5)
    )

@router.callback_query(F.data == "adm_upload_done", F.from_user.id.in_(ADMIN_IDS))
async def process_upload_done(callback: CallbackQuery, state: FSMContext):
    """Завершение загрузки файлов (возврат в админ-панель)."""
    await state.clear()
    stats = await database.get_stats()
    await callback.answer("Загрузка файлов успешно завершена!")
    await send_admin_panel(callback.message, stats, edit=True)

@router.callback_query(F.data == "admin_edit_services", F.from_user.id.in_(ADMIN_IDS))
async def show_edit_services(callback: CallbackQuery, state: FSMContext):
    """Показ списка сервисов для редактирования."""
    await state.clear()
    services = await database.get_services()
    if not services:
        await callback.answer("⚠️ В базе данных пока нет ни одного сервиса!", show_alert=True)
        return

    try:
        await callback.message.bot(EditCustomMessageMedia(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            media={"type": "photo", "media": IMG_ADMIN, "caption": "<b><tg-emoji emoji-id=\"5877485980901971030\">⚙️</tg-emoji> Выбери сервис для редактирования:</b>", "parse_mode": "HTML"},
            reply_markup=get_services_keyboard(services)
        ))
        await callback.answer()
    except Exception:
        pass

@router.callback_query(F.data.startswith("adm_serv_"), F.from_user.id.in_(ADMIN_IDS))
async def edit_service_menu(callback: CallbackQuery):
    """Показ меню редактирования выбранного сервиса."""
    service_id = int(callback.data.split("_")[2])
    service = await database.get_service_by_id(service_id)

    if not service:
        await callback.answer('❌ Сервис не найден!', show_alert=True)
        return

    count = await database.get_available_accounts_count(service_id)
    category_name = "Без категории"
    if service.get("category_id"):
        category = await database.get_category_by_id(service["category_id"])
        if category:
            category_name = category["name"]

    text = (
        f"<b><tg-emoji emoji-id=\"5877485980901971030\">⚙️</tg-emoji> Редактирование сервиса: {service['name']}</b>\n\n"
        f"├ <tg-emoji emoji-id=\"5967456680940671207\">📂</tg-emoji> <b>Категория:</b> <code>{category_name}</code>\n"
        f"├ <tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> <b>Текущая базовая цена:</b> <code>${service['base_price']:.2f}</code>\n"
        f"╰ <tg-emoji emoji-id=\"5967456680940671207\">📦</tg-emoji> <b>В наличии свободных аккаунтов:</b> <code>{count} шт.</code>"
    )
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN, "caption": text, "parse_mode": "HTML"},
        reply_markup=get_service_edit_menu(service_id)
    ))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_setcat_"), F.from_user.id.in_(ADMIN_IDS))
async def start_set_service_category(callback: CallbackQuery):
    """Выбор новой категории для сервиса."""
    service_id = int(callback.data.split("_")[2])
    service = await database.get_service_by_id(service_id)
    if not service:
        await callback.answer("❌ Сервис не найден!", show_alert=True)
        return

    categories = await database.get_all_categories()
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_ADMIN,
            "caption": f"<b><tg-emoji emoji-id=\"5967456680940671207\">📂</tg-emoji> Выбери категорию для {service['name']}:</b>",
            "parse_mode": "HTML"
        },
        reply_markup=get_category_pick_keyboard(
            categories,
            prefix=f"adm_assigncat_{service_id}_",
            include_none=True,
            back_callback=f"adm_serv_{service_id}"
        )
    ))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_assigncat_"), F.from_user.id.in_(ADMIN_IDS))
async def process_assign_service_category(callback: CallbackQuery):
    """Привязка сервиса к выбранной категории."""
    parts = callback.data.split("_")
    # adm_assigncat_{service_id}_{category_id|none}
    service_id = int(parts[2])
    raw_cat = parts[3]
    category_id = None if raw_cat == "none" else int(raw_cat)

    service = await database.get_service_by_id(service_id)
    if not service:
        await callback.answer("❌ Сервис не найден!", show_alert=True)
        return

    if category_id is not None:
        category = await database.get_category_by_id(category_id)
        if not category:
            await callback.answer("❌ Категория не найдена!", show_alert=True)
            return

    await database.assign_service_to_category(service_id, category_id)
    await callback.answer("Категория обновлена!", show_alert=True)

    count = await database.get_available_accounts_count(service_id)
    category_name = "Без категории"
    if category_id is not None:
        category = await database.get_category_by_id(category_id)
        if category:
            category_name = category["name"]

    text = (
        f"<b><tg-emoji emoji-id=\"5877485980901971030\">⚙️</tg-emoji> Редактирование сервиса: {service['name']}</b>\n\n"
        f"├ <tg-emoji emoji-id=\"5967456680940671207\">📂</tg-emoji> <b>Категория:</b> <code>{category_name}</code>\n"
        f"├ <tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> <b>Текущая базовая цена:</b> <code>${service['base_price']:.2f}</code>\n"
        f"╰ <tg-emoji emoji-id=\"5967456680940671207\">📦</tg-emoji> <b>В наличии свободных аккаунтов:</b> <code>{count} шт.</code>"
    )
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN, "caption": text, "parse_mode": "HTML"},
        reply_markup=get_service_edit_menu(service_id)
    ))

@router.callback_query(F.data == "admin_categories", F.from_user.id.in_(ADMIN_IDS))
async def process_admin_categories(callback: CallbackQuery, state: FSMContext):
    """Список категорий каталога."""
    await state.clear()
    categories = await database.get_all_categories()
    text = (
        "<b><tg-emoji emoji-id=\"5967456680940671207\">📂</tg-emoji> Категории каталога</b>\n\n"
        "Выбери категорию для редактирования или создай новую."
    )
    if not categories:
        text = (
            "<b><tg-emoji emoji-id=\"5967456680940671207\">📂</tg-emoji> Категории каталога</b>\n\n"
            "Пока нет ни одной категории. Создай первую!"
        )

    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN, "caption": text, "parse_mode": "HTML"},
        reply_markup=get_categories_manage_keyboard(categories)
    ))
    await callback.answer()

@router.callback_query(F.data == "admin_create_category", F.from_user.id.in_(ADMIN_IDS))
async def process_create_category_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания категории."""
    await state.set_state(AdminCategory.waiting_for_name)
    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отмена",
            "callback_data": "admin_categories",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_ADMIN,
            "caption": "<b><tg-emoji emoji-id=\"5879841310902324730\">📝</tg-emoji> Введи название новой категории:</b>",
            "parse_mode": "HTML"
        },
        reply_markup=cancel_kb
    ))
    await callback.answer()

@router.message(AdminCategory.waiting_for_name, F.from_user.id.in_(ADMIN_IDS))
async def process_create_category_name(message: Message, state: FSMContext):
    """Создание категории по названию."""
    name = (message.text or "").strip()
    if not name:
        await message.answer("<b>❌ Название не может быть пустым. Введи название:</b>", parse_mode="HTML")
        return

    try:
        await database.create_category(name)
    except aiosqlite.IntegrityError:
        await message.answer("<b>❌ Категория с таким названием уже существует. Введи другое:</b>", parse_mode="HTML")
        return

    await state.clear()
    await message.answer(f"<b>✅ Категория <code>{name}</code> создана!</b>", parse_mode="HTML")

    categories = await database.get_all_categories()
    await message.bot(SendCustomPhoto(
        chat_id=message.chat.id,
        photo=IMG_ADMIN,
        caption="<b><tg-emoji emoji-id=\"5967456680940671207\">📂</tg-emoji> Категории каталога</b>",
        parse_mode="HTML",
        reply_markup=get_categories_manage_keyboard(categories)
    ))

@router.callback_query(F.data.startswith("adm_catview_"), F.from_user.id.in_(ADMIN_IDS))
async def process_category_menu(callback: CallbackQuery):
    """Меню конкретной категории."""
    category_id = int(callback.data.split("_")[2])
    category = await database.get_category_by_id(category_id)
    if not category:
        await callback.answer("❌ Категория не найдена!", show_alert=True)
        return

    services = await database.get_services_by_category(category_id)
    text = (
        f"<b><tg-emoji emoji-id=\"5967456680940671207\">📂</tg-emoji> Категория: {category['name']}</b>\n\n"
        f"<b>Товаров в категории:</b> <code>{len(services)}</code> шт."
    )
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN, "caption": text, "parse_mode": "HTML"},
        reply_markup=get_category_edit_menu(category_id)
    ))
    await callback.answer()

@router.callback_query(F.data.startswith("adm_catrename_"), F.from_user.id.in_(ADMIN_IDS))
async def process_category_rename_start(callback: CallbackQuery, state: FSMContext):
    """Начало переименования категории."""
    category_id = int(callback.data.split("_")[2])
    category = await database.get_category_by_id(category_id)
    if not category:
        await callback.answer("❌ Категория не найдена!", show_alert=True)
        return

    await state.update_data(category_id=category_id)
    await state.set_state(AdminCategory.waiting_for_rename)
    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отмена",
            "callback_data": f"adm_catview_{category_id}",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_ADMIN,
            "caption": f"<b>Введи новое название для категории <code>{category['name']}</code>:</b>",
            "parse_mode": "HTML"
        },
        reply_markup=cancel_kb
    ))
    await callback.answer()

@router.message(AdminCategory.waiting_for_rename, F.from_user.id.in_(ADMIN_IDS))
async def process_category_rename(message: Message, state: FSMContext):
    """Сохранение нового названия категории."""
    name = (message.text or "").strip()
    if not name:
        await message.answer("<b>❌ Название не может быть пустым. Введи название:</b>", parse_mode="HTML")
        return

    data = await state.get_data()
    category_id = data["category_id"]

    try:
        await database.update_category_name(category_id, name)
    except aiosqlite.IntegrityError:
        await message.answer("<b>❌ Категория с таким названием уже существует. Введи другое:</b>", parse_mode="HTML")
        return

    await state.clear()
    await message.answer(f"<b>✅ Категория переименована в <code>{name}</code>!</b>", parse_mode="HTML")

    services = await database.get_services_by_category(category_id)
    text = (
        f"<b><tg-emoji emoji-id=\"5967456680940671207\">📂</tg-emoji> Категория: {name}</b>\n\n"
        f"<b>Товаров в категории:</b> <code>{len(services)}</code> шт."
    )
    await message.bot(SendCustomMessage(
        chat_id=message.chat.id,
        text=text,
        parse_mode="HTML",
        reply_markup=get_category_edit_menu(category_id)
    ))

@router.callback_query(F.data.startswith("adm_catdel_"), F.from_user.id.in_(ADMIN_IDS))
async def process_category_delete(callback: CallbackQuery):
    """Удаление категории (товары остаются без категории)."""
    category_id = int(callback.data.split("_")[2])
    category = await database.get_category_by_id(category_id)
    if not category:
        await callback.answer("❌ Категория не найдена!", show_alert=True)
        return

    await database.delete_category(category_id)
    await callback.answer(f"Категория {category['name']} удалена!", show_alert=True)

    categories = await database.get_all_categories()
    text = (
        "<b><tg-emoji emoji-id=\"5967456680940671207\">📂</tg-emoji> Категории каталога</b>\n\n"
        "Выбери категорию для редактирования или создай новую."
    )
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN, "caption": text, "parse_mode": "HTML"},
        reply_markup=get_categories_manage_keyboard(categories)
    ))

@router.callback_query(F.data.startswith("adm_editprice_"), F.from_user.id.in_(ADMIN_IDS))
async def start_edit_price(callback: CallbackQuery, state: FSMContext):
    """Запуск FSM изменения цены."""
    service_id = int(callback.data.split("_")[2])
    service = await database.get_service_by_id(service_id)

    await state.update_data(service_id=service_id, service_name=service["name"])
    await state.set_state(AdminEditService.waiting_for_new_price)

    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отмена",
            "callback_data": f"adm_serv_{service_id}",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_ADMIN,
            "caption": f"<b><tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> Введи новую базовую цену для сервиса {service['name']} в $ (например, <code>1.99</code>):</b>",
            "parse_mode": "HTML"
        },
        reply_markup=cancel_kb
    ))
    await callback.answer()

@router.message(AdminEditService.waiting_for_new_price, F.from_user.id.in_(ADMIN_IDS))
async def process_new_price(message: Message, state: FSMContext):
    """Сохранение новой базовой цены."""
    try:
        new_price = float(message.text.replace(",", "."))
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer('<tg-emoji emoji-id="5778527486270770928">❌</tg-emoji> Неверный формат цены. Введи положительное число:')
        return

    data = await state.get_data()
    service_id = data["service_id"]
    service_name = data["service_name"]

    await database.update_service_price(service_id, new_price)
    await state.clear()

    await message.answer(f"<b><tg-emoji emoji-id=\"5951665890079544884\">✅</tg-emoji> Базовая цена для сервиса {service_name} обновлена до ${new_price:.2f}!</b>", parse_mode="HTML")

    count = await database.get_available_accounts_count(service_id)
    text = (
        f"<b><tg-emoji emoji-id=\"5877485980901971030\">⚙️</tg-emoji> Редактирование сервиса: {service_name}</b>\n\n"
        f"├ <tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> <b>Текущая базовая цена:</b> <code>${new_price:.2f}</code>\n"
        f"╰ <tg-emoji emoji-id=\"5967456680940671207\">📦</tg-emoji> <b>В наличии свободных аккаунтов:</b> <code>{count} шт.</code>"
    )
    await message.bot(SendCustomMessage(
        chat_id=message.chat.id,
        text=text,
        parse_mode="HTML",
        reply_markup=get_service_edit_menu(service_id)
    ))

@router.callback_query(F.data.startswith("adm_upload_"), F.from_user.id.in_(ADMIN_IDS))
async def start_upload_more(callback: CallbackQuery, state: FSMContext):
    """Запуск FSM дозагрузки аккаунтов/файлов."""
    service_id = int(callback.data.split("_")[2])
    service = await database.get_service_by_id(service_id)

    await state.update_data(service_id=service_id, service_name=service["name"], service_type=service["type"])
    await state.set_state(AdminEditService.waiting_for_new_credentials)

    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отмена",
            "callback_data": f"adm_serv_{service_id}",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }

    if service["type"] == "text":
        caption = f"<b><tg-emoji emoji-id=\"5967456680940671207\">📥</tg-emoji> Отправь новые аккаунты для {service['name']} (каждый с новой строки в формате <code>логин:пароль</code>):</b>"
    else:
        caption = f"<b><tg-emoji emoji-id=\"5967456680940671207\">📥</tg-emoji> Отправь новые файлы (.json или .txt) для {service['name']}:</b>"

    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_ADMIN,
            "caption": caption,
            "parse_mode": "HTML"
        },
        reply_markup=cancel_kb
    ))
    await callback.answer()

@router.message(AdminEditService.waiting_for_new_credentials, F.text, F.from_user.id.in_(ADMIN_IDS))
async def process_new_credentials_text(message: Message, state: FSMContext):
    data = await state.get_data()
    service_type = data.get("service_type", "text")
    if service_type != "text":
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Этот сервис ожидает загрузку файлов (.json / .txt), а не текст!</b>", parse_mode="HTML")
        return

    text_data = message.text.strip()
    lines = [line.strip() for line in text_data.split("\n") if line.strip()]

    if not lines:
        await message.answer('<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Строки пусты. Пришли список аккаунтов:</b>', parse_mode="HTML")
        return

    service_id = data["service_id"]
    service_name = data["service_name"]

    await database.add_accounts(service_id, lines)
    await state.clear()

    await message.answer(f"<b><tg-emoji emoji-id=\"5951665890079544884\">🎉</tg-emoji> Успешно догружено {len(lines)} шт. аккаунтов для сервиса {service_name}!</b>", parse_mode="HTML")

    service = await database.get_service_by_id(service_id)
    count = await database.get_available_accounts_count(service_id)
    text = (
        f"<b><tg-emoji emoji-id=\"5877485980901971030\">⚙️</tg-emoji> Редактирование сервиса: {service_name}</b>\n\n"
        f"├ <tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> <b>Текущая базовая цена:</b> <code>${service['base_price']:.2f}</code>\n"
        f"╰ <tg-emoji emoji-id=\"5967456680940671207\">📦</tg-emoji> <b>В наличии свободных аккаунтов:</b> <code>{count} шт.</code>"
    )
    await message.bot(SendCustomMessage(
        chat_id=message.chat.id,
        text=text,
        parse_mode="HTML",
        reply_markup=get_service_edit_menu(service_id)
    ))

@router.message(AdminEditService.waiting_for_new_credentials, F.document, F.from_user.id.in_(ADMIN_IDS))
async def process_new_credentials_file(message: Message, state: FSMContext):
    data = await state.get_data()
    service_type = data.get("service_type", "text")
    if service_type != "file":
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Этот сервис ожидает загрузку текстовых аккаунтов, а не файлов!</b>", parse_mode="HTML")
        return

    file_name = message.document.file_name or ""
    if not (file_name.lower().endswith(".json") or file_name.lower().endswith(".txt")):
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Разрешены только файлы формата .json или .txt!</b>", parse_mode="HTML")
        return

    service_id = data["service_id"]
    service_name = data["service_name"]
    user_id = message.from_user.id

    await database.add_accounts(service_id, [message.document.file_id])

    if user_id not in upload_buffers:
        upload_buffers[user_id] = {
            "files": [],
            "task": None,
            "service_id": service_id,
            "service_name": service_name,
            "is_edit": True
        }

    upload_buffers[user_id]["files"].append(file_name)

    if upload_buffers[user_id]["task"]:
        upload_buffers[user_id]["task"].cancel()

    upload_buffers[user_id]["task"] = asyncio.create_task(
        send_upload_summary_after_delay(message, state, user_id, 1.5)
    )

@router.callback_query(F.data == "adm_edit_upload_done", F.from_user.id.in_(ADMIN_IDS))
async def process_edit_upload_done(callback: CallbackQuery, state: FSMContext):
    """Завершение дозагрузки файлов (возврат в меню редактирования сервиса)."""
    data = await state.get_data()
    service_id = data["service_id"]
    service_name = data["service_name"]
    await state.clear()

    service = await database.get_service_by_id(service_id)
    count = await database.get_available_accounts_count(service_id)
    text = (
        f"<b><tg-emoji emoji-id=\"5877485980901971030\">⚙️</tg-emoji> Редактирование сервиса: {service_name}</b>\n\n"
        f"├ <tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> <b>Текущая базовая цена:</b> <code>${service['base_price']:.2f}</code>\n"
        f"╰ <tg-emoji emoji-id=\"5967456680940671207\">📦</tg-emoji> <b>В наличии свободных аккаунтов:</b> <code>{count} шт.</code>"
    )
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN, "caption": text, "parse_mode": "HTML"},
        reply_markup=get_service_edit_menu(service_id)
    ))
    await callback.answer("Загрузка файлов успешно завершена!")

@router.callback_query(F.data.startswith("adm_delserv_"), F.from_user.id.in_(ADMIN_IDS))
async def process_delete_service(callback: CallbackQuery):
    """Удаление сервиса и его аккаунтов."""
    service_id = int(callback.data.split("_")[2])
    service = await database.get_service_by_id(service_id)

    if not service:
        await callback.answer('❌ Сервис не найден!', show_alert=True)
        return

    await database.delete_service(service_id)
    await callback.answer(f"Сервис {service['name']} успешно удален!", show_alert=True)

    services = await database.get_services()
    if not services:

        stats = await database.get_stats()
        await send_admin_panel(callback.message, stats, edit=True)
        return

    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN, "caption": "<b><tg-emoji emoji-id=\"5877485980901971030\">⚙️</tg-emoji> Выбери сервис для редактирования:</b>", "parse_mode": "HTML"},
        reply_markup=get_services_keyboard(services)
    ))

@router.callback_query(F.data == "admin_promos", F.from_user.id.in_(ADMIN_IDS))
async def process_admin_promos(callback: CallbackQuery, state: FSMContext):
    """Показ списка промокодов."""
    await state.clear()
    promos = await database.get_all_promocodes()

    if promos:
        lines = []
        for p in promos:
            lines.append(
                f"<code>{p['code']}</code> — ${p['amount']:.2f} "
                f"({p['current_activations']}/{p['max_activations']})"
            )
        promo_list = "\n".join(lines)
        text = f"<b><tg-emoji emoji-id=\"5879841310902324730\">🎟</tg-emoji> Промокоды:</b>\n\n{promo_list}"
    else:
        text = "<b><tg-emoji emoji-id=\"5879841310902324730\">🎟</tg-emoji> Промокоды:</b>\n\nПока нет созданных промокодов."

    kb = {
        "inline_keyboard": [
            [{"text": "Создать промокод", "callback_data": "admin_create_promo", "icon_custom_emoji_id": "5879841310902324730"}],
            [{"text": "Назад в меню", "callback_data": "admin_to_menu", "icon_custom_emoji_id": "5877536313623711363"}]
        ]
    }

    if promos:
        for p in promos:
            kb["inline_keyboard"].insert(-1, [
                {"text": f"Удалить {p['code']}", "callback_data": f"admin_delpromo_{p['id']}", "icon_custom_emoji_id": "5778527486270770928"}
            ])

    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN, "caption": text, "parse_mode": "HTML"},
        reply_markup=kb
    ))
    await callback.answer()

@router.callback_query(F.data == "admin_create_promo", F.from_user.id.in_(ADMIN_IDS))
async def process_create_promo_start(callback: CallbackQuery, state: FSMContext):
    """Начало создания промокода."""
    await state.set_state(AdminPromo.waiting_for_promo_data)
    cancel_kb = {"inline_keyboard": [[{"text": "Отмена", "callback_data": "admin_promos", "icon_custom_emoji_id": "5778527486270770928"}]]}
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN,
               "caption": "<b><tg-emoji emoji-id=\"5879841310902324730\">🎟</tg-emoji> Создание промокода</b>\n\n<b>Введи сумму и количество активаций через запятую.</b>\n\n<b>Пример:</b> <code>0.50,5</code>\n<b>(промокод на $0.50 с 5 активациями)</b>",
               "parse_mode": "HTML"},
        reply_markup=cancel_kb
    ))
    await callback.answer()

@router.message(AdminPromo.waiting_for_promo_data, F.text, F.from_user.id.in_(ADMIN_IDS))
async def process_create_promo_data(message: Message, state: FSMContext):
    """Обработка ввода данных промокода."""
    text = message.text.strip().replace(" ", "")
    parts = text.split(",")
    if len(parts) != 2:
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Неверный формат. Введи: <code>сумма,количество</code>\nПример: <code>0.50,5</code></b>", parse_mode="HTML")
        return
    try:
        amount = float(parts[0])
        max_act = int(parts[1])
        if amount <= 0 or max_act <= 0:
            raise ValueError
    except ValueError:
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Сумма должна быть положительным числом, количество — целым числом > 0.</b>", parse_mode="HTML")
        return

    code = await database.create_promocode(amount, max_act)
    await state.clear()

    await message.answer(
        f"<b><tg-emoji emoji-id=\"5951665890079544884\">✅</tg-emoji> Промокод создан!</b>\n\n"
        f"<b><tg-emoji emoji-id=\"5879841310902324730\">🎟</tg-emoji> Код:</b> <code>{code}</code>\n"
        f"<b><tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> Сумма:</b> <code>${amount:.2f}</code>\n"
        f"<b><tg-emoji emoji-id=\"5920344347152224466\">👥</tg-emoji> Активаций:</b> <code>{max_act}</code>",
        parse_mode="HTML"
    )
    stats = await database.get_stats()
    await send_admin_panel(message, stats)

@router.callback_query(F.data.startswith("admin_delpromo_"), F.from_user.id.in_(ADMIN_IDS))
async def process_delete_promo(callback: CallbackQuery):
    """Удаление промокода."""
    promo_id = int(callback.data.split("_")[2])
    await database.delete_promocode(promo_id)
    await callback.answer("Промокод удален!", show_alert=True)

    promos = await database.get_all_promocodes()
    if promos:
        lines = [f"<code>{p['code']}</code> — ${p['amount']:.2f} ({p['current_activations']}/{p['max_activations']})" for p in promos]
        text = f"<b><tg-emoji emoji-id=\"5879841310902324730\">🎟</tg-emoji> Промокоды:</b>\n\n" + "\n".join(lines)
    else:
        text = "<b><tg-emoji emoji-id=\"5879841310902324730\">🎟</tg-emoji> Промокоды:</b>\n\nПока нет созданных промокодов."
    kb = {"inline_keyboard": [[{"text": "Создать промокод", "callback_data": "admin_create_promo", "icon_custom_emoji_id": "5879841310902324730"}], [{"text": "Назад в меню", "callback_data": "admin_to_menu", "icon_custom_emoji_id": "5877536313623711363"}]]}
    if promos:
        for p in promos:
            kb["inline_keyboard"].insert(-1, [{"text": f"Удалить {p['code']}", "callback_data": f"admin_delpromo_{p['id']}", "icon_custom_emoji_id": "5778527486270770928"}])
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id, message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN, "caption": text, "parse_mode": "HTML"}, reply_markup=kb
    ))

async def send_user_info_card(target, user_id: int, edit: bool = False):
    user = await database.get_user_info(user_id)
    if not user:
        return False

    purchases_count = await database.get_user_purchases_count(user_id)
    username = f"@{user['username']}" if user.get('username') else "нет"
    first_name = user.get('first_name') or "Без имени"
    tickets_count = user.get("support_tickets_count", 0)

    text = (
        f"<b><tg-emoji emoji-id=\"5920344347152224466\">👤</tg-emoji> Профиль пользователя {first_name}:</b>\n"
        f"├  <tg-emoji emoji-id=\"5936017305585586269\">🪪</tg-emoji> <b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"├  <tg-emoji emoji-id=\"5920344347152224466\">👤</tg-emoji> <b>Юзернейм:</b> {username}\n"
        f"├  <tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> <b>Баланс:</b> <code>${user.get('balance', 0.0):.2f}</code>\n"
        f"├  <tg-emoji emoji-id=\"5879841310902324730\">🎟</tg-emoji> <b>Всего тикетов:</b> <code>{tickets_count}</code> <b>шт.</b>\n"
        f"╰  <tg-emoji emoji-id=\"5985493993100679671\">🛒</tg-emoji> <b>Куплено аккаунтов:</b> <code>{purchases_count}</code> <b>шт.</b>"
    )

    kb = themed({
        "inline_keyboard": [
            [
                {"text": "💰 Изменить баланс", "callback_data": f"admin_usr_change_bal_{user_id}"},
                {"text": "📋 История покупок", "callback_data": f"admin_usr_purch_hist_{user_id}"}
            ],
            [
                {"text": "В меню админа", "callback_data": "admin_to_menu", "icon_custom_emoji_id": "5877536313623711363"}
            ]
        ]
    })

    if edit:
        if isinstance(target, CallbackQuery):
            try:
                await target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
            except Exception:
                try:
                    await target.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb)
                except Exception:
                    await target.message.delete()
                    await target.message.bot.send_message(chat_id=target.message.chat.id, text=text, parse_mode="HTML", reply_markup=kb)
        else:
            try:
                await target.edit_text(text, parse_mode="HTML", reply_markup=kb)
            except Exception:
                try:
                    await target.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb)
                except Exception:
                    await target.delete()
                    await target.bot.send_message(chat_id=target.chat.id, text=text, parse_mode="HTML", reply_markup=kb)
    else:
        if isinstance(target, CallbackQuery):
            await target.message.bot.send_message(chat_id=target.message.chat.id, text=text, parse_mode="HTML", reply_markup=kb)
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=kb)
    return True

@router.callback_query(F.data == "admin_user_info", F.from_user.id.in_(ADMIN_IDS))
async def process_user_info_start(callback: CallbackQuery, state: FSMContext):
    """Начало поиска информации о пользователе."""
    await state.set_state(AdminUserInfoState.waiting_for_user_id)
    cancel_kb = {"inline_keyboard": [[{"text": "Отмена", "callback_data": "admin_to_menu", "icon_custom_emoji_id": "5778527486270770928"}]]}
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id, message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN,
               "caption": "<b><tg-emoji emoji-id=\"5920344347152224466\">🔍</tg-emoji> Поиск пользователя</b>\n\n<b>Введи Telegram ID или @username пользователя:</b>",
               "parse_mode": "HTML"},
        reply_markup=cancel_kb
    ))
    await callback.answer()

@router.message(AdminUserInfoState.waiting_for_user_id, F.text, F.from_user.id.in_(ADMIN_IDS))
async def process_user_info_search(message: Message, state: FSMContext):
    """Поиск пользователя по ID или юзернейму."""
    query = message.text.strip()
    user_id = None

    if query.startswith("@") or not query.isdigit():
        username = query.lstrip("@")
        user = await database.get_user_by_username(username)
        if user:
            user_id = user["user_id"]
    else:

        if query.isdigit():
            user_id = int(query)
            user = await database.get_user_info(user_id)
            if not user:
                user_id = None

    if not user_id:
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Пользователь не найден. Попробуй ввести другой ID или @username.</b>", parse_mode="HTML")
        return

    await state.clear()
    await send_user_info_card(message, user_id)

@router.callback_query(F.data.startswith("admin_usr_change_bal_"), F.from_user.id.in_(ADMIN_IDS))
async def process_user_info_balance_change_start(callback: CallbackQuery, state: FSMContext):
    """Запрос изменения баланса."""
    user_id = int(callback.data.split("_")[4])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminUserInfoState.waiting_for_balance_change)

    cancel_kb = themed({"inline_keyboard": [[{"text": "Отмена", "callback_data": f"admin_usr_view_{user_id}"}]]})
    text = (
        f"<b><tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> Изменение баланса (ID: <code>{user_id}</code>)</b>\n\n"
        f"Введи значение для изменения баланса:\n"
        f"• Используй знак <b>+</b> для прибавления денег (например: <code>+1</code> или <code>1.5</code>)\n"
        f"• Используй знак <b>-</b> для списания денег (например: <code>-1.5</code>)"
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=cancel_kb)
    except Exception:
        try:
            await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=cancel_kb)
        except Exception:
            await callback.message.delete()
            await callback.message.bot.send_message(chat_id=callback.message.chat.id, text=text, parse_mode="HTML", reply_markup=cancel_kb)

    await callback.answer()

@router.callback_query(F.data.startswith("admin_usr_view_"), F.from_user.id.in_(ADMIN_IDS))
async def process_user_info_view_back(callback: CallbackQuery, state: FSMContext):
    """Возврат к просмотру карточки юзера."""
    await state.clear()
    user_id = int(callback.data.split("_")[3])
    await send_user_info_card(callback, user_id, edit=True)
    await callback.answer()

@router.message(AdminUserInfoState.waiting_for_balance_change, F.text, F.from_user.id.in_(ADMIN_IDS))
async def process_user_info_balance_change_data(message: Message, state: FSMContext):
    """Обработка ввода суммы для изменения баланса."""
    input_text = message.text.strip().replace(" ", "").replace(",", ".")

    try:
        change_amount = float(input_text)
    except ValueError:
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Пожалуйста, введи корректное число (например: +1.5 или -1.0).</b>", parse_mode="HTML")
        return

    state_data = await state.get_data()
    user_id = state_data.get("target_user_id")

    if not user_id:
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Ошибка сессии. Попробуй найти пользователя заново через меню.</b>", parse_mode="HTML")
        await state.clear()
        return

    user = await database.get_user_info(user_id)
    if not user:
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Пользователь не найден в базе данных.</b>", parse_mode="HTML")
        await state.clear()
        return

    await database.add_user_balance(user_id, change_amount)
    await state.clear()

    action_text = "начислен" if change_amount >= 0 else "списан"
    abs_amount = abs(change_amount)

    await message.answer(
        f"<b><tg-emoji emoji-id=\"5951665890079544884\">✅</tg-emoji> Баланс успешно изменен!</b>\n"
        f"Пользователю (ID: <code>{user_id}</code>) {action_text} <code>${abs_amount:.2f}</code>.",
        parse_mode="HTML"
    )

    try:
        if change_amount > 0:
            await message.bot.send_message(
                chat_id=user_id,
                text=f"<b><tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> Твой баланс пополнен администратором на <code>${change_amount:.2f}</code>!</b>",
                parse_mode="HTML"
            )
        elif change_amount < 0:
            await message.bot.send_message(
                chat_id=user_id,
                text=f"<b><tg-emoji emoji-id=\"5985346521103604145\">📉</tg-emoji> Администратор списал с твоего баланса <code>${abs_amount:.2f}</code>!</b>",
                parse_mode="HTML"
            )
    except Exception:
        pass

    await send_user_info_card(message, user_id)

@router.callback_query(F.data.startswith("admin_usr_purch_hist_"), F.from_user.id.in_(ADMIN_IDS))
async def process_user_info_purchase_history(callback: CallbackQuery):
    """Просмотр истории покупок пользователя."""
    user_id = int(callback.data.split("_")[4])
    purchases = await database.get_user_purchases_history(user_id, limit=10)

    if not purchases:
        await callback.answer("❌ У этого пользователя нет покупок.", show_alert=True)
        return

    import datetime

    text_lines = [f"<b><tg-emoji emoji-id=\"5875206779196935950\">📋</tg-emoji> Последние 10 покупок пользователя (ID: <code>{user_id}</code>):</b>"]
    for i, o in enumerate(purchases, 1):
        dt = datetime.datetime.fromtimestamp(o["purchased_at"], datetime.timezone(datetime.timedelta(hours=3)))
        time_str = dt.strftime("%d.%m.%Y %H:%M")
        text_lines.append(
            f"<b><code>{i}</code>. {o['service_name']} ({o['category']})</b>\n"
            f"<b>├ Кол-во: <code>{o['quantity']}</code> шт. | Сумма: <code>${o['total_price']:.2f}</code></b>\n"
            f"<b>╰ Время: <code>{time_str}</code></b>"
        )

    text = "\n\n".join(text_lines)
    kb = themed({"inline_keyboard": [[{"text": "К профилю", "callback_data": f"admin_usr_view_{user_id}", "icon_custom_emoji_id": "5877536313623711363"}]]})

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        try:
            await callback.message.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await callback.message.delete()
            await callback.message.bot.send_message(chat_id=callback.message.chat.id, text=text, parse_mode="HTML", reply_markup=kb)

    await callback.answer()

@router.callback_query(F.data == "admin_broadcast", F.from_user.id.in_(ADMIN_IDS))
async def process_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Начало рассылки."""
    await state.set_state(AdminBroadcast.waiting_for_broadcast_content)
    cancel_kb = {"inline_keyboard": [[{"text": "Отмена", "callback_data": "admin_to_menu", "icon_custom_emoji_id": "5778527486270770928"}]]}
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id, message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_ADMIN,
               "caption": "<b><tg-emoji emoji-id=\"5988023995125993550\">📢</tg-emoji> Рассылка</b>\n\n<b>Отправь сообщение для рассылки.</b>\n\n<b>Можно отправить:</b>\n<b>• Только текст</b>\n<b>• Только фото</b>\n<b>• Фото + подпись (текст)</b>",
               "parse_mode": "HTML"},
        reply_markup=cancel_kb
    ))
    await callback.answer()

@router.message(AdminBroadcast.waiting_for_broadcast_content, F.from_user.id.in_(ADMIN_IDS))
async def process_broadcast_content(message: Message, state: FSMContext):
    """Получение контента для рассылки (текст, фото, или фото+текст)."""
    broadcast_data = {}

    if message.photo:
        broadcast_data["photo"] = message.photo[-1].file_id
        broadcast_data["caption"] = message.caption or ""
        broadcast_data["type"] = "photo"
        preview = f"📷 <b>Фото</b>" + (f"\n\n{message.caption}" if message.caption else "")
    elif message.text:
        broadcast_data["text"] = message.text
        broadcast_data["type"] = "text"
        preview = message.text
    else:
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Поддерживается только текст или фото. Попробуй ещё раз.</b>", parse_mode="HTML")
        return

    user_ids = await database.get_all_user_ids()
    await state.update_data(broadcast_data=broadcast_data)
    await state.set_state(AdminBroadcast.waiting_for_broadcast_confirm)

    confirm_kb = themed({
        "inline_keyboard": [
            [{"text": "✅ Подтвердить отправку", "callback_data": "admin_broadcast_confirm"}],
            [{"text": "Отмена", "callback_data": "admin_to_menu", "icon_custom_emoji_id": "5778527486270770928"}]
        ]
    })
    await message.answer(
        f"<b><tg-emoji emoji-id=\"5988023995125993550\">📢</tg-emoji> Превью рассылки:</b>\n\n{preview}\n\n"
        f"<b><tg-emoji emoji-id=\"5920344347152224466\">👥</tg-emoji> Получателей:</b> <code>{len(user_ids)}</code> <b>чел.</b>\n\n"
        f"<b>Подтверди отправку:</b>",
        parse_mode="HTML",
        reply_markup=confirm_kb
    )

@router.callback_query(F.data == "admin_broadcast_confirm", F.from_user.id.in_(ADMIN_IDS))
async def process_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и выполнение рассылки."""
    data = await state.get_data()
    broadcast_data = data.get("broadcast_data")
    if not broadcast_data:
        await callback.answer("❌ Данные рассылки не найдены.", show_alert=True)
        await state.clear()
        return

    await state.clear()
    user_ids = await database.get_all_user_ids()

    await callback.message.edit_text("<b><tg-emoji emoji-id=\"5988023995125993550\">📢</tg-emoji> Рассылка запущена... <tg-emoji emoji-id=\"5823396554345549784\">⏳</tg-emoji></b>", parse_mode="HTML")
    await callback.answer()

    sent = 0
    blocked = 0
    for uid in user_ids:
        try:
            if broadcast_data["type"] == "photo":
                orig_caption = broadcast_data.get("caption", "")
                bold_caption = f"<b>{orig_caption}</b>" if orig_caption else ""
                await callback.message.bot.send_photo(
                    chat_id=uid, photo=broadcast_data["photo"],
                    caption=bold_caption, parse_mode="HTML"
                )
            else:
                bold_text = f"<b>{broadcast_data['text']}</b>"
                await callback.message.bot.send_message(
                    chat_id=uid, text=bold_text, parse_mode="HTML"
                )
            sent += 1
        except Exception:
            blocked += 1
        await asyncio.sleep(0.05)

    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"5988023995125993550\">📢</tg-emoji> Рассылка завершена!</b>\n\n"
        f"<b><tg-emoji emoji-id=\"5951665890079544884\">✅</tg-emoji> Доставлено:</b> <code>{sent}</code>\n"
        f"<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Не доставлено:</b> <code>{blocked}</code>",
        parse_mode="HTML"
    )
    stats = await database.get_stats()
    await send_admin_panel(callback.message, stats)

async def notify_admins_about_purchase(bot, user_id: int, username: str, service_name: str, quantity: int, total_price: float):
    """Отправляет уведомление всем админам о новой покупке."""
    text = (
        f'<b><tg-emoji emoji-id="5985493993100679671">🛒</tg-emoji> Новая покупка!</b>\n\n'
        f'<tg-emoji emoji-id="5920344347152224466">👤</tg-emoji> <b>Покупатель:</b> {username} (<code>{user_id}</code>)\n'
        f'<tg-emoji emoji-id="5967456680940671207">📦</tg-emoji> <b>Товар:</b> <b>{service_name}</b>\n'
        f'<tg-emoji emoji-id="5900120651825418289">🔢</tg-emoji> <b>Количество:</b> <code>{quantity}</code> <b>шт.</b>\n'
        f'<tg-emoji emoji-id="5967390100357648692">💵</tg-emoji> <b>Сумма:</b> <code>${total_price:.2f}</code>'
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except Exception:
            pass

async def show_tickets_list(target, edit_msg: Optional[Message] = None):
    """Показывает список всех открытых тикетов в виде инлайн-кнопок."""
    tickets = await database.get_open_tickets()
    if not tickets:
        text = "<b><tg-emoji emoji-id=\"5879841310902324730\">🎟</tg-emoji> Неотвеченных обращений в поддержку не найдено!</b>"
        kb = themed({
            "inline_keyboard": [[{
                "text": "В меню админа",
                "callback_data": "admin_to_menu",
                "icon_custom_emoji_id": "5877536313623711363"
            }]]
        })
        if edit_msg:
            try:
                await edit_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
            except Exception:
                try:
                    await edit_msg.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb)
                except Exception:
                    await edit_msg.delete()
                    await edit_msg.bot.send_message(chat_id=edit_msg.chat.id, text=text, parse_mode="HTML", reply_markup=kb)
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=kb)
        return

    keyboard = []
    for ticket in tickets:
        t_id = ticket["id"]

        user_info = await database.get_user_info(ticket["user_id"])
        if user_info:
            username = f"@{user_info['username']}" if user_info.get("username") else user_info.get("first_name", "Без имени")
        else:
            username = ticket.get("username") or f"ID: {ticket['user_id']}"

        time_str = ticket["created_at"].split(" ")[1][:5] if " " in ticket["created_at"] else ticket["created_at"]

        button_text = f"🎟 #{t_id} | {username} | {time_str}"
        keyboard.append([{"text": button_text, "callback_data": f"admin_view_ticket_{t_id}"}])

    keyboard.append([{"text": "В меню админа", "callback_data": "admin_to_menu", "icon_custom_emoji_id": "5877536313623711363"}])

    text = "<b><tg-emoji emoji-id=\"5879841310902324730\">🎟</tg-emoji> Список открытых обращений в поддержку:</b>"
    kb = themed({"inline_keyboard": keyboard})

    if edit_msg:
        try:
            await edit_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            try:
                await edit_msg.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await edit_msg.delete()
                await edit_msg.bot.send_message(chat_id=edit_msg.chat.id, text=text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "admin_tickets_list", F.from_user.id.in_(ADMIN_IDS))
async def callback_admin_tickets_list(callback: CallbackQuery):
    """Кнопка возврата к списку открытых тикетов."""
    await show_tickets_list(callback.message, edit_msg=callback.message)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_view_ticket_"), F.from_user.id.in_(ADMIN_IDS))
async def callback_admin_view_ticket(callback: CallbackQuery):
    """Просмотр конкретного тикета со всей информацией."""
    ticket_id = int(callback.data.split("_")[3])
    ticket = await database.get_ticket_by_id(ticket_id)

    if not ticket:
        await callback.answer("❌ Обращение не найдено.", show_alert=True)
        await show_tickets_list(callback.message, edit_msg=callback.message)
        return

    user_id = ticket["user_id"]
    username = ticket["username"] or "Без имени"

    user_info = await database.get_user_info(user_id)
    tickets_count = user_info.get("support_tickets_count", 1) if user_info else 1

    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT created_at FROM support_tickets WHERE user_id = ? AND id < ? ORDER BY id DESC LIMIT 1",
            (user_id, ticket_id)
        ) as cursor:
            row = await cursor.fetchone()
            prev_time = row["created_at"] if row else "Предыдущих обращений не найдено"

    ticket_header = (
        f"<b><tg-emoji emoji-id=\"5988023995125993550\">💬</tg-emoji> Обращение #{ticket_id} в поддержку!</b>\n\n"
        f"<b>Отправитель:</b> {username} (<code>{user_id}</code>)\n"
        f"<b>Всего обращений:</b> <code>{tickets_count}</code>\n"
        f"<b>Предыдущее обращение:</b> <code>{prev_time}</code>\n\n"
        f"<b>Сообщение:</b>\n"
        f"<b>{ticket['message_text'] if ticket['message_text'] else '(без текста)'}</b>"
    )

    ticket_kb = themed({
        "inline_keyboard": [
            [
                {"text": "Ответить", "callback_data": f"admin_reply_ticket_{ticket_id}", "icon_custom_emoji_id": "5879841310902324730"},
                {"text": "Закрыть без ответа", "callback_data": f"admin_close_ticket_{ticket_id}", "icon_custom_emoji_id": "5778527486270770928"}
            ],
            [
                {"text": "Последние сообщения", "callback_data": f"admin_view_history_{ticket_id}", "icon_custom_emoji_id": "5879841310902324730"}
            ],
            [
                {"text": "Назад к списку", "callback_data": "admin_tickets_list", "icon_custom_emoji_id": "5877536313623711363"}
            ]
        ]
    })

    if ticket["media_type"] == "photo" and ticket["file_id"]:
        await callback.message.delete()
        await callback.message.bot.send_photo(
            chat_id=callback.message.chat.id,
            photo=ticket["file_id"],
            caption=ticket_header,
            parse_mode="HTML",
            reply_markup=ticket_kb
        )
    elif ticket["media_type"] == "document" and ticket["file_id"]:
        await callback.message.delete()
        await callback.message.bot.send_document(
            chat_id=callback.message.chat.id,
            document=ticket["file_id"],
            caption=ticket_header,
            parse_mode="HTML",
            reply_markup=ticket_kb
        )
    else:
        try:
            await callback.message.edit_text(ticket_header, parse_mode="HTML", reply_markup=ticket_kb)
        except Exception:
            await callback.message.delete()
            await callback.message.bot.send_message(
                chat_id=callback.message.chat.id,
                text=ticket_header,
                parse_mode="HTML",
                reply_markup=ticket_kb
            )

    await callback.answer()

@router.callback_query(F.data.startswith("admin_view_history_"), F.from_user.id.in_(ADMIN_IDS))
async def callback_admin_view_history(callback: CallbackQuery):
    """Просмотр истории последних 10 сообщений пользователя."""
    ticket_id = int(callback.data.split("_")[3])
    ticket = await database.get_ticket_by_id(ticket_id)

    if not ticket:
        await callback.answer("❌ Обращение не найдено.", show_alert=True)
        return

    user_id = ticket["user_id"]

    history_rows = await database.get_user_tickets_history(user_id, limit=10)

    if not history_rows:
        await callback.answer("История переписки пуста.", show_alert=True)
        return

    history_rows = list(reversed(history_rows))

    user_info = await database.get_user_info(user_id)
    if user_info:
        username = f"@{user_info['username']}" if user_info.get("username") else user_info.get("first_name", "Без имени")
    else:
        username = ticket["username"] or f"ID: {user_id}"

    history_text = f"<b><tg-emoji emoji-id=\"5879841310902324730\">📜</tg-emoji> Последние сообщения {username} ({user_id}):</b>\n\n"

    for row in history_rows:
        t_id = row["id"]
        created_at = row["created_at"]
        msg_text = row["message_text"] or "(медиафайл без текста)"

        history_text += f"<b><tg-emoji emoji-id=\"5920344347152224466\">👤</tg-emoji> {username} (<code>{user_id}</code>) [{created_at}]:</b>\n"
        history_text += f"<i>{msg_text}</i>\n\n"

        if row["status"] == "replied" and row["reply_text"]:
            replied_at = row["replied_at"] or "Время неизвестно"
            history_text += f"<b><tg-emoji emoji-id=\"5988023995125993550\">💬</tg-emoji> Поддержка [{replied_at}]:</b>\n"
            history_text += f"<i>{row['reply_text']}</i>\n\n"
        elif row["status"] == "closed":
            history_text += f"<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Обращение #{t_id} закрыто без ответа</b>\n\n"

    history_text += "----------------------------------"

    back_kb = {
        "inline_keyboard": [[
            {"text": "Назад к тикету", "callback_data": f"admin_view_ticket_{ticket_id}", "icon_custom_emoji_id": "5877536313623711363"}
        ]]
    }

    try:
        await callback.message.edit_text(history_text, parse_mode="HTML", reply_markup=back_kb)
    except Exception:
        await callback.message.delete()
        await callback.message.bot.send_message(
            chat_id=callback.message.chat.id,
            text=history_text,
            parse_mode="HTML",
            reply_markup=back_kb
        )

    await callback.answer()

@router.callback_query(F.data.startswith("admin_close_ticket_"), F.from_user.id.in_(ADMIN_IDS))
async def callback_admin_close_ticket(callback: CallbackQuery):
    """Закрытие обращения без ответа пользователю."""
    ticket_id = int(callback.data.split("_")[3])

    await database.update_ticket_status(ticket_id, "closed")

    await callback.answer(f"✅ Обращение #{ticket_id} успешно закрыто!", show_alert=True)
    await show_tickets_list(callback.message, edit_msg=callback.message)

@router.callback_query(F.data.startswith("admin_reply_ticket_"), F.from_user.id.in_(ADMIN_IDS))
async def start_admin_reply(callback: CallbackQuery, state: FSMContext):
    """Начало ввода ответа пользователю администратором."""
    ticket_id = int(callback.data.split("_")[3])
    ticket = await database.get_ticket_by_id(ticket_id)

    if not ticket:
        await callback.answer("❌ Обращение не найдено.", show_alert=True)
        return

    user_id = ticket["user_id"]

    await state.update_data(reply_target_user_id=user_id, reply_target_ticket_id=ticket_id)
    await state.set_state(AdminReplyState.waiting_for_reply)

    user_info = await database.get_user_info(user_id)
    if user_info:
        username = f"@{user_info['username']}" if user_info.get("username") else user_info.get("first_name", "Без имени")
        user_display = f"{username} (<code>{user_id}</code>)"
    else:
        user_display = f"@{ticket['username']}" if ticket.get("username") else f"<code>{user_id}</code>"

    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отмена",
            "callback_data": f"admin_view_ticket_{ticket_id}",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.bot.send_message(
        chat_id=callback.message.chat.id,
        text=f"<b><tg-emoji emoji-id=\"5879841310902324730\">✍️</tg-emoji> Введи сообщение для ответа пользователю {user_display} на Обращение #{ticket_id}:</b>",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await callback.answer()

@router.message(AdminReplyState.waiting_for_reply, F.from_user.id.in_(ADMIN_IDS))
async def process_admin_reply_message(message: Message, state: FSMContext):
    """Отправка ответа администратора пользователю."""
    data = await state.get_data()
    user_id = data.get("reply_target_user_id")
    ticket_id = data.get("reply_target_ticket_id")
    await state.clear()

    if not user_id or not ticket_id:
        await message.answer("<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Ошибка: не найден тикет или ID пользователя для ответа.</b>", parse_mode="HTML")
        return

    header = "<b><tg-emoji emoji-id=\"5988023995125993550\">💬</tg-emoji> Ответ от поддержки:</b>\n\n"

    try:
        if message.photo:
            caption = header + f"<b>{message.caption if message.caption else ''}</b>"
            await message.bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=caption,
                parse_mode="HTML"
            )
        elif message.document:
            caption = header + f"<b>{message.caption if message.caption else ''}</b>"
            await message.bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=caption,
                parse_mode="HTML"
            )
        else:
            text_content = message.text if message.text else "(пустой ответ)"
            await message.bot.send_message(
                chat_id=user_id,
                text=header + f"<b>{text_content}</b>",
                parse_mode="HTML"
            )

        text_content = message.text if message.text else (message.caption if message.caption else "(медиафайл без текста)")
        await database.save_ticket_reply(ticket_id, text_content)
        await message.answer(f"<b><tg-emoji emoji-id=\"5951665890079544884\">✅</tg-emoji> Ответ успешно отправлен пользователю, Обращение #{ticket_id} закрыто!</b>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending reply to user {user_id}: {e}")
        await message.answer(f"<b><tg-emoji emoji-id=\"5778527486270770928\">❌</tg-emoji> Не удалось отправить ответ пользователю {user_id}. Возможно, он заблокировал бота.</b>", parse_mode="HTML")

    await show_tickets_list(message)
