import logging

logger = logging.getLogger(__name__)

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, LinkPreviewOptions
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import database
from keyboards.user_kb import (
    get_main_menu,
    get_buy_services_keyboard,
    get_categories_keyboard,
    get_payment_keyboard,
    get_history_keyboard,
    get_profile_kb,
    get_payment_systems_kb
)
from services.payment import PaymentService
from services.custom_methods import SendCustomMessage, SendCustomPhoto, EditCustomMessageText, EditCustomMessageMedia
from config import ADMIN_IDS

IMG_MAIN_MENU = "https://i.ibb.co/YFnCkZS1/image.png"
IMG_STOCK = "https://i.ibb.co/nNv34cwX/image.png"
IMG_PROFILE = "https://i.ibb.co/9HQJ6ss6/image.png"
IMG_BUY = "https://i.ibb.co/5x8RpBBz/image.png"

router = Router()

class UserBuy(StatesGroup):
    waiting_for_service = State()
    waiting_for_category = State()
    waiting_for_quantity = State()
    waiting_for_payment = State()

class TopUpState(StatesGroup):
    enter_amount = State()
    choose_system = State()

class PromoState(StatesGroup):
    enter_code = State()

class UserSupportState(StatesGroup):
    waiting_for_message = State()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start."""
    await state.clear()

    await database.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    welcome_text = (
        f'<b><tg-emoji emoji-id="5258260149037965799">💼</tg-emoji> Добро пожаловать в Funeral Shop, {message.from_user.full_name}!</b>\n\n'
        "Используй кнопки меню ниже для навигации:"
    )
    await message.bot(SendCustomPhoto(
        chat_id=message.chat.id,
        photo=IMG_MAIN_MENU,
        caption=welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu()
    ))

@router.callback_query(F.data == "user_to_menu")
async def callback_user_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню пользователя."""
    await state.clear()
    welcome_text = (
        f'<b><tg-emoji emoji-id="5258260149037965799">💼</tg-emoji> Добро пожаловать в Funeral Shop, {callback.from_user.full_name}!</b>\n\n'
        "Используй кнопки меню ниже для навигации:"
    )
    if callback.message.photo:
        await callback.message.bot(EditCustomMessageMedia(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            media={"type": "photo", "media": IMG_MAIN_MENU, "caption": welcome_text, "parse_mode": "HTML"},
            reply_markup=get_main_menu()
        ))
    else:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.bot(SendCustomPhoto(
            chat_id=callback.message.chat.id,
            photo=IMG_MAIN_MENU,
            caption=welcome_text,
            parse_mode="HTML",
            reply_markup=get_main_menu()
        ))
    await callback.answer()

@router.callback_query(F.data == "check_stock")
async def process_check_stock(callback: CallbackQuery):
    """Обработка кнопки 'Наличие товаров' с умной псевдографикой."""
    services = await database.get_services()
    service_blocks = []

    for service in services:
        accounts = await database.get_available_accounts(service["id"])

        if service.get("type", "text") == "file":
            count = len(accounts)
            if count == 0:
                continue
            price = service["base_price"]
            service_block = [
                f"🔹 <b>{service['name']}</b>",
                f"╰ 📁 <b>В наличии:</b> <code>{count}</code> <b>шт. -</b> <code>{price:.2f}$</code>"
            ]
            service_blocks.append("\n".join(service_block))
        else:
            categories = database.group_accounts_by_category(service["base_price"], accounts)

            active_categories = {name: info for name, info in categories.items() if len(info["accounts"]) > 0}

            if not active_categories:
                continue

            service_block = [f"🔹 <b>{service['name']}</b>"]
            cat_items = list(active_categories.items())
            num_cats = len(cat_items)

            for idx, (cat_name, info) in enumerate(cat_items):
                count = len(info["accounts"])
                price = info["price"]
                display_name = "Свежие (0-12ч)" if cat_name == "Свежие" else f"{cat_name} отлёжка"

                if num_cats == 1:
                    prefix = "╰"
                else:
                    if idx == 0:
                        prefix = "╭"
                    elif idx == num_cats - 1:
                        prefix = "╰"
                    else:
                        prefix = "├"

                service_block.append(f"{prefix} 🔸 <b>[{display_name}]:</b> <code>{count}</code> <b>шт. -</b> <code>{price:.2f}$</code>")

            service_blocks.append("\n".join(service_block))

    title = '<tg-emoji emoji-id="5967456680940671207">🗃</tg-emoji> <b>Наличие товаров</b>'
    if not service_blocks:
        text = f"{title}\n\n<b>К сожалению, на данный момент товаров нет в наличии.</b>"
    else:
        text = f"{title}\n\n" + "\n───\n".join(service_blocks)

    back_kb = {
        "inline_keyboard": [[{
            "text": "Назад в меню",
            "callback_data": "user_to_menu",
            "icon_custom_emoji_id": "5877536313623711363"
        }]]
    }

    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_STOCK, "caption": text, "parse_mode": "HTML"},
        reply_markup=back_kb
    ))
    await callback.answer()

@router.callback_query(F.data == "user_profile")
async def process_user_profile(callback: CallbackQuery, state: FSMContext):
    """Отображение профиля пользователя в виде псевдографики."""
    await state.clear()
    user_info = await database.get_user_info(callback.from_user.id)

    if not user_info:
        await database.add_user(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        user_info = await database.get_user_info(callback.from_user.id)

    purchased_count = await database.get_user_purchases_count(callback.from_user.id)

    profile_text = (
        f"╭ <tg-emoji emoji-id=\"5920344347152224466\">👤</tg-emoji> <b>Имя:</b> <code>{user_info['first_name']}</code>\n"
        f"├  <tg-emoji emoji-id=\"5936017305585586269\">🪪</tg-emoji> <b>Telegram ID:</b> <code>{user_info['user_id']}</code>\n"
        f"├  <tg-emoji emoji-id=\"5778318458802409852\">💰</tg-emoji> <b>Баланс:</b> <code>${user_info['balance']:.2f}</code>\n"
        f"╰ <tg-emoji emoji-id=\"5985493993100679671\">🗑</tg-emoji> <b>Куплено аккаунтов:</b> <code>{purchased_count}</code> <b>шт.</b>"
    )

    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_PROFILE, "caption": profile_text, "parse_mode": "HTML"},
        reply_markup=get_profile_kb()
    ))
    await callback.answer()

@router.callback_query(F.data == "history_purchases")
async def process_history_purchases(callback: CallbackQuery):
    """Показ истории покупок пользователя (последние 10)."""
    orders = await database.get_user_orders(callback.from_user.id, limit=10)

    if not orders:
        back_kb = {
            "inline_keyboard": [[{
                "text": "Назад в профиль",
                "callback_data": "user_profile",
                "icon_custom_emoji_id": "5877536313623711363"
            }]]
        }
        await callback.message.bot(EditCustomMessageMedia(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            media={"type": "photo", "media": IMG_PROFILE, "caption": "📜 Пока нет совершённых покупок в магазине.", "parse_mode": "HTML"},
            reply_markup=back_kb
        ))
        await callback.answer()
        return

    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_PROFILE,
            "caption": '<tg-emoji emoji-id="5875206779196935950">📁</tg-emoji> <b>История твоих покупок (последние 10):</b>\n\n<i>Нажми на покупку, чтобы получить данные аккаунтов:</i>',
            "parse_mode": "HTML"
        },
        reply_markup=get_history_keyboard(orders)
    ))
    await callback.answer()

@router.callback_query(F.data.startswith("show_ord_"))
async def process_show_order(callback: CallbackQuery):
    """Выдача купленных ранее данных из заказа."""
    order_id = int(callback.data.split("_")[2])
    order = await database.get_order_by_id(order_id)

    if not order:
        await callback.answer("❌ Заказ не найден!", show_alert=True)
        return

    if order["user_id"] != callback.from_user.id:
        await callback.answer("❌ Нет доступа к этому заказу!", show_alert=True)
        return

    service = await database.get_service_by_name(order["service_name"])
    if service and service.get("type") == "file":

        file_ids = [fid.strip() for fid in order["delivered_data"].split(",") if fid.strip()]
        await callback.message.answer(
            f'<tg-emoji emoji-id="6005570495603282482">🔑</tg-emoji> <b>Файлы заказа #{order["id"]} ({order["service_name"]}):</b>',
            parse_mode="HTML"
        )
        for file_id in file_ids:
            try:
                await callback.message.answer_document(document=file_id)
            except Exception as e:
                logger.error(f"Error re-sending document in history: {e}")
        await callback.answer("Файлы отправлены!")
    else:

        await callback.message.answer(
            f'<tg-emoji emoji-id="6005570495603282482">🔑</tg-emoji> <b>Данные заказа #{order["id"]} ({order["service_name"]}):</b>\n'
            f"<pre><code>{order['delivered_data']}</code></pre>",
            parse_mode="HTML"
        )
        await callback.answer("Данные отправлены!")

@router.callback_query(F.data == "activate_promo")
async def process_activate_promo_start(callback: CallbackQuery, state: FSMContext):
    """Начало ввода промокода."""
    await state.set_state(PromoState.enter_code)
    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отмена",
            "callback_data": "user_profile",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_PROFILE,
            "caption": '<tg-emoji emoji-id="5879841310902324730">✏️</tg-emoji> <b>Введи промокод:</b>',
            "parse_mode": "HTML"
        },
        reply_markup=cancel_kb
    ))
    await callback.answer()

@router.message(PromoState.enter_code)
async def process_activate_promo_code(message: Message, state: FSMContext):
    """Обработка введённого промокода."""
    if not message.text:
        await message.answer("❌ Введи промокод текстом:")
        return

    code = message.text.strip()
    result = await database.activate_promocode(code, message.from_user.id)

    await state.clear()

    if result["success"]:
        await message.answer(
            f'<tg-emoji emoji-id="5951665890079544884">✅</tg-emoji> <b>{result["message"]}</b>\n\n'
            f'<tg-emoji emoji-id="5967390100357648692">💵</tg-emoji> <b>На баланс начислено:</b> <code>${result["amount"]:.2f}</code>',
            parse_mode="HTML"
        )

        activator = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        notify_text = (
            f'<b><tg-emoji emoji-id="5879841310902324730">🎟</tg-emoji> Активация промокода!</b>\n\n'
            f'<tg-emoji emoji-id="5920344347152224466">👤</tg-emoji> <b>Пользователь:</b> {activator} (<code>{message.from_user.id}</code>)\n'
            f'<tg-emoji emoji-id="5879841310902324730">🎟</tg-emoji> <b>Промокод:</b> <code>{code}</code>\n'
            f'<tg-emoji emoji-id="5967390100357648692">💵</tg-emoji> <b>Сумма:</b> <code>${result["amount"]:.2f}</code>'
        )
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(chat_id=admin_id, text=notify_text, parse_mode="HTML")
            except Exception:
                pass
    else:
        await message.answer(
            f'<tg-emoji emoji-id="5985346521103604145">❌</tg-emoji> <b>{result["message"]}</b>',
            parse_mode="HTML"
        )

@router.callback_query(F.data == "buy_accounts")
async def process_buy_accounts(callback: CallbackQuery, state: FSMContext):
    """Шаг 1: Выбор сервиса."""
    await state.clear()
    await state.set_state(UserBuy.waiting_for_service)

    services = await database.get_services()
    if not services:
        back_kb = {
            "inline_keyboard": [[{
                "text": "Назад в меню",
                "callback_data": "user_to_menu",
                "icon_custom_emoji_id": "5877536313623711363"
            }]]
        }
        await callback.message.bot(EditCustomMessageMedia(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            media={"type": "photo", "media": IMG_BUY, "caption": "⚠️ В магазине пока нет доступных услуг.", "parse_mode": "HTML"},
            reply_markup=back_kb
        ))
        await callback.answer()
        return

    available_counts = {}
    has_available = False
    for service in services:
        count = await database.get_available_accounts_count(service["id"])
        available_counts[service["id"]] = count
        if count > 0:
            has_available = True

    if not has_available:
        back_kb = {
            "inline_keyboard": [[{
                "text": "Назад в меню",
                "callback_data": "user_to_menu",
                "icon_custom_emoji_id": "5877536313623711363"
            }]]
        }
        await callback.message.bot(EditCustomMessageMedia(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            media={"type": "photo", "media": IMG_BUY, "caption": "⚠️ В магазине пока нет доступных товаров.", "parse_mode": "HTML"},
            reply_markup=back_kb
        ))
        await callback.answer()
        return

    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_BUY, "caption": '<tg-emoji emoji-id="5258200019495821936">🗳</tg-emoji> <b>Выбери интересующий сервис:</b>', "parse_mode": "HTML"},
        reply_markup=get_buy_services_keyboard(services, available_counts)
    ))
    await callback.answer()

@router.callback_query(F.data.startswith("buy_serv_"), UserBuy.waiting_for_service)
async def process_buy_service_select(callback: CallbackQuery, state: FSMContext):
    """Шаг 2: Выбор категории отлёжки или переход к выбору количества (для файлов)."""
    service_id = int(callback.data.split("_")[2])
    service = await database.get_service_by_id(service_id)

    if not service:
        await callback.answer("❌ Сервис не найден!", show_alert=True)
        return

    accounts = await database.get_available_accounts(service_id)
    if not accounts:
        back_kb = {
            "inline_keyboard": [[{
                "text": "К списку услуг",
                "callback_data": "buy_accounts",
                "icon_custom_emoji_id": "5877536313623711363"
            }]]
        }
        await callback.message.bot(EditCustomMessageMedia(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            media={
                "type": "photo",
                "media": IMG_BUY,
                "caption": f"⚠️ К сожалению, товары для сервиса <b>{service['name']}</b> закончились.",
                "parse_mode": "HTML"
            },
            reply_markup=back_kb
        ))
        await callback.answer()
        return

    if service.get("type", "text") == "file":
        await state.update_data(
            service_id=service_id,
            service_name=service["name"],
            service_type="file",
            price=service["base_price"],
            accounts=accounts
        )
        await state.set_state(UserBuy.waiting_for_quantity)

        cancel_kb = {
            "inline_keyboard": [[{
                "text": "Отменить покупку",
                "callback_data": "buy_accounts",
                "icon_custom_emoji_id": "5778527486270770928"
            }]]
        }
        await callback.message.bot(EditCustomMessageMedia(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            media={
                "type": "photo",
                "media": IMG_BUY,
                "caption": f'<tg-emoji emoji-id="5877485980901971030">📊</tg-emoji> <b>Вы выбрали:</b> <b>{service["name"]}</b>\n'
                           f'<tg-emoji emoji-id="5776219138917668486">📈</tg-emoji> <b>Цена за 1 шт:</b> <code>${service["base_price"]:.2f}</code>\n'
                           f'<tg-emoji emoji-id="5956561916573782596">📄</tg-emoji> <b>Доступно:</b> <code>{len(accounts)}</code> <b>шт.</b>\n\n'
                           f'<b><tg-emoji emoji-id="5879841310902324730">✏️</tg-emoji> Введи количество файлов, которое хочешь приобрести:</b>',
                "parse_mode": "HTML"
            },
            reply_markup=cancel_kb
        ))
        await callback.answer()
        return

    categories = database.group_accounts_by_category(service["base_price"], accounts)

    active_categories = {name: info for name, info in categories.items() if len(info["accounts"]) > 0}

    if not active_categories:
        back_kb = {
            "inline_keyboard": [[{
                "text": "К списку услуг",
                "callback_data": "buy_accounts",
                "icon_custom_emoji_id": "5877536313623711363"
            }]]
        }
        await callback.message.bot(EditCustomMessageMedia(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            media={
                "type": "photo",
                "media": IMG_BUY,
                "caption": f"⚠️ В данный момент нет свободных категорий для <b>{service['name']}</b>.",
                "parse_mode": "HTML"
            },
            reply_markup=back_kb
        ))
        await callback.answer()
        return

    await state.update_data(
        service_id=service_id,
        service_name=service["name"],
        service_type="text",
        categories=active_categories
    )
    await state.set_state(UserBuy.waiting_for_category)

    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_BUY,
            "caption": f'<tg-emoji emoji-id="5877485980901971030">📊</tg-emoji> <b>Выбери категорию отлёжки для {service["name"]}:</b>',
            "parse_mode": "HTML"
        },
        reply_markup=get_categories_keyboard(service_id, active_categories)
    ))
    await callback.answer()

@router.callback_query(F.data.startswith("buy_cat_"), UserBuy.waiting_for_category)
async def process_buy_category_select(callback: CallbackQuery, state: FSMContext):
    """Шаг 3: Ввод количества аккаунтов для текстовых товаров."""
    cat_idx = int(callback.data.split("_")[2])

    data = await state.get_data()
    categories = data["categories"]
    service_name = data["service_name"]

    cat_keys = list(categories.keys())
    if cat_idx >= len(cat_keys):
        await callback.answer('❌ Произошла ошибка выбора категории!', show_alert=True)
        return

    category_name = cat_keys[cat_idx]
    category_info = categories[category_name]

    price = category_info["price"]
    available_accs = category_info["accounts"]

    await state.update_data(
        category_name=category_name,
        price=price,
        accounts=available_accs
    )

    await state.set_state(UserBuy.waiting_for_quantity)

    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отменить покупку",
            "callback_data": "buy_accounts",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }

    display_cat = "Свежие" if category_name == "Свежие" else category_name
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_BUY,
            "caption": f'<tg-emoji emoji-id="5877485980901971030">📊</tg-emoji> <b>Вы выбрали:</b> <b>{service_name} [{display_cat}]</b>\n'
                       f'<tg-emoji emoji-id="5776219138917668486">📈</tg-emoji> <b>Цена за 1 шт:</b> <code>${price:.2f}</code>\n'
                       f'<tg-emoji emoji-id="5956561916573782596">📄</tg-emoji> <b>Доступно:</b> <code>{len(available_accs)}</code> <b>шт.</b>\n\n'
                       f'<b><tg-emoji emoji-id="5879841310902324730">✏️</tg-emoji> Введи количество аккаунтов, которое хочешь приобрести:</b>',
            "parse_mode": "HTML"
        },
        reply_markup=cancel_kb
    ))
    await callback.answer()

@router.message(UserBuy.waiting_for_quantity)
async def process_buy_quantity(message: Message, state: FSMContext):
    """Шаг 4: Подтверждение покупки."""
    if not message.text:
        await message.answer('<tg-emoji emoji-id="5778527486270770928">❌</tg-emoji> Введи число:')
        return

    data = await state.get_data()
    available_accs = data["accounts"]
    price = data["price"]
    service_name = data["service_name"]
    category_name = data.get("category_name")
    service_type = data.get("service_type", "text")
    max_count = len(available_accs)

    try:
        quantity = int(message.text)
        if quantity <= 0 or quantity > max_count:
            raise ValueError
    except ValueError:
        await message.answer(
            f'<tg-emoji emoji-id="5778527486270770928">❌</tg-emoji> Введено некорректное число или товара нет в таком количестве.\n'
            f"Введи целое число от 1 до {max_count}:"
        )
        return

    selected_accounts = available_accs[:quantity]
    total_price = quantity * price

    await state.update_data(
        quantity=quantity,
        selected_accounts=selected_accounts,
        total_price=total_price
    )

    await state.set_state(UserBuy.waiting_for_payment)

    if service_type == "file":
        display_item = f"<b>{service_name}</b>"
    else:
        display_cat = "Свежие" if category_name == "Свежие" else category_name
        display_item = f"<b>{service_name} [{display_cat}]</b>"

    checkout_text = (
        f'<tg-emoji emoji-id="5877485980901971030">📊</tg-emoji> <b>Детали заказа:</b>\n\n'
        f'<tg-emoji emoji-id="5967456680940671207">🗃</tg-emoji> <b>Товар:</b> {display_item}\n'
        f'<tg-emoji emoji-id="5900120651825418289">🔢</tg-emoji> <b>Количество:</b> <code>{quantity}</code> <b>шт.</b>\n'
        f'<tg-emoji emoji-id="5776219138917668486">📈</tg-emoji> <b>Цена за 1 шт:</b> <code>${price:.2f}</code>\n'
        f'<tg-emoji emoji-id="5974217466270716579">💵</tg-emoji> <b>Итого к оплате:</b> <code>${total_price:.2f}</code>\n\n'
        "<b>Подтверди заказ и соверши оплату, нажав на кнопку ниже:</b>"
    )

    await message.bot(SendCustomPhoto(
        chat_id=message.chat.id,
        photo=IMG_BUY,
        caption=checkout_text,
        parse_mode="HTML",
        reply_markup=get_payment_keyboard()
    ))

@router.callback_query(F.data == "pay_now", UserBuy.waiting_for_payment)
async def process_payment(callback: CallbackQuery, state: FSMContext):
    """Оплата с баланса и выдача товара с записью в таблицу orders."""
    data = await state.get_data()
    selected_accounts = data["selected_accounts"]
    price = data["price"]
    service_name = data["service_name"]
    category_name = data.get("category_name")
    service_type = data.get("service_type", "text")
    quantity = data["quantity"]
    total_price_usd = data["total_price"]

    user_info = await database.get_user_info(callback.from_user.id)
    if not user_info:
        await callback.answer("Ошибка: Профиль не найден.", show_alert=True)
        return

    total_price_usd = round(total_price_usd, 2)
    user_balance = round(user_info["balance"], 2)

    if not user_info or user_balance < total_price_usd:
        await callback.answer(
            f'❌ Недостаточно средств на балансе!\n\n'
            f"Стоимость: ${total_price_usd:.2f}\n"
            f"Твой баланс: ${user_balance:.2f}\n\n"
            f"Пополни баланс в профиле.",
            show_alert=True
        )
        return

    creds_list = [acc["credentials"] for acc in selected_accounts]
    if service_type == "file":
        creds_text = ",".join(creds_list)
    else:
        creds_text = "\n".join(creds_list)

    account_ids = [acc["id"] for acc in selected_accounts]

    try:
        await database.sell_accounts_and_create_order(
            user_id=callback.from_user.id,
            service_name=service_name,
            category_name=category_name or "Файлы",
            quantity=quantity,
            total_price=total_price_usd,
            account_ids=account_ids,
            credentials_text=creds_text
        )
    except ValueError as e:
        err_msg = str(e)
        if err_msg == "Some accounts are already sold":
            await callback.answer(
                '❌ Один или несколько аккаунтов уже выкуплены другим пользователем.\n\n'
                "Списание средств не произошло. Собери корзину заново.",
                show_alert=True
            )
            await state.clear()
            back_to_menu_kb = {
                "inline_keyboard": [[{
                    "text": "В главное меню",
                    "callback_data": "user_to_menu",
                    "icon_custom_emoji_id": "5877536313623711363"
                }]]
            }
            await callback.message.bot(EditCustomMessageMedia(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                media={
                    "type": "photo",
                    "media": IMG_BUY,
                    "caption": '<tg-emoji emoji-id="5778527486270770928">❌</tg-emoji> Покупка отменена: часть выбранных аккаунтов уже продана.',
                    "parse_mode": "HTML"
                },
                reply_markup=back_to_menu_kb
            ))
        elif err_msg == "Insufficient balance":
            await callback.answer(
                '❌ Недостаточно средств! Баланс изменился.',
                show_alert=True
            )
        else:
            await callback.answer('❌ Ошибка обработки заказа. Попробуй еще раз.', show_alert=True)
        return
    except Exception:
        await callback.answer('❌ Ошибка обработки заказа. Попробуй еще раз.', show_alert=True)
        return

    logger.info(f"PURCHASE: user={callback.from_user.id} service={service_name} qty={quantity} total=${total_price_usd:.2f}")

    buyer_name = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.first_name
    notify_text = (
        f'<b><tg-emoji emoji-id="5985493993100679671">🛒</tg-emoji> Новая покупка!</b>\n\n'
        f'<tg-emoji emoji-id="5920344347152224466">👤</tg-emoji> <b>Покупатель:</b> {buyer_name} (<code>{callback.from_user.id}</code>)\n'
        f'<tg-emoji emoji-id="5967456680940671207">📦</tg-emoji> <b>Товар:</b> <b>{service_name}</b>\n'
        f'<tg-emoji emoji-id="5900120651825418289">🔢</tg-emoji> <b>Количество:</b> <code>{quantity}</code> <b>шт.</b>\n'
        f'<tg-emoji emoji-id="5967390100357648692">💵</tg-emoji> <b>Сумма:</b> <code>${total_price_usd:.2f}</code>'
    )
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(chat_id=admin_id, text=notify_text, parse_mode="HTML")
        except Exception:
            pass

    await state.clear()

    back_kb = {
        "inline_keyboard": [[{
            "text": "В главное меню",
            "callback_data": "user_to_menu",
            "icon_custom_emoji_id": "5877536313623711363"
        }]]
    }

    await callback.message.delete()

    if service_type == "file":
        success_text = (
            '<tg-emoji emoji-id="5823396554345549784">✔️</tg-emoji> <b>Оплата прошла успешно!</b>\n\n'
            f'<tg-emoji emoji-id="5875206779196935950">📁</tg-emoji> <b>Куплено файлов: {quantity} шт.</b>\n'
        )
        await callback.message.bot(SendCustomMessage(
            chat_id=callback.message.chat.id,
            text=success_text,
            parse_mode="HTML",
            reply_markup=back_kb
        ))

        for file_id in creds_list:
            try:
                await callback.message.answer_document(document=file_id)
            except Exception as e:
                logger.error(f"Error sending document: {e}")
    else:
        success_text = (
            '<tg-emoji emoji-id="5823396554345549784">✔️</tg-emoji> <b>Оплата прошла успешно!</b>\n\n'
            f'<tg-emoji emoji-id="5877597667231534929">🗒</tg-emoji> <b>Твои аккаунты:</b>\n'
            f"<pre><code>{creds_text}</code></pre>\n"
            "Спасибо за покупку!"
        )
        await callback.message.bot(SendCustomMessage(
            chat_id=callback.message.chat.id,
            text=success_text,
            parse_mode="HTML",
            reply_markup=back_kb
        ))

    await callback.answer()

@router.callback_query(F.data == "top_up_balance")
async def start_top_up(callback: CallbackQuery, state: FSMContext):
    """Начало сценария пополнения баланса."""
    await callback.answer()
    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отмена",
            "callback_data": "user_profile",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }
    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={
            "type": "photo",
            "media": IMG_PROFILE,
            "caption": '<tg-emoji emoji-id="5877396173135811032">⌨</tg-emoji> <b>Введи сумму пополнения в $:</b>',
            "parse_mode": "HTML"
        },
        reply_markup=cancel_kb
    ))
    await state.set_state(TopUpState.enter_amount)

@router.message(TopUpState.enter_amount)
async def process_amount(message: Message, state: FSMContext):
    """Валидация суммы пополнения."""
    if not message.text:
        await message.answer('<tg-emoji emoji-id="5778527486270770928">❌</tg-emoji> Введи сумму числом:')
        return

    text = message.text.strip().replace(",", ".")
    try:
        amount = float(text)
        if amount < 0.5:
            raise ValueError
        amount = round(amount, 2)
    except ValueError:
        await message.answer('<tg-emoji emoji-id="5778527486270770928">❌</tg-emoji> Минимальная сумма пополнения - <b>$0.50</b>. Введи корректное число:')
        return

    await state.update_data(amount=amount)

    await message.bot(SendCustomPhoto(
        chat_id=message.chat.id,
        photo=IMG_PROFILE,
        caption=f"💳 Сумма пополнения: <b>${amount:.2f}</b>\nВыбери платежную систему для оплаты:",
        parse_mode="HTML",
        reply_markup=get_payment_systems_kb()
    ))
    await state.set_state(TopUpState.choose_system)

@router.callback_query(TopUpState.choose_system, F.data.in_({"pay_cryptobot", "pay_xrocket"}))
async def process_payment_system(callback: CallbackQuery, state: FSMContext):
    """Создание инвойса в выбранной платежной системе."""
    await callback.answer()
    data = await state.get_data()
    amount = data.get("amount")
    user_id = callback.from_user.id

    system = callback.data
    invoice = None

    await callback.message.bot(EditCustomMessageMedia(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        media={"type": "photo", "media": IMG_PROFILE, "caption": "⏳ Генерируем счет на оплату...", "parse_mode": "HTML"}
    ))

    if system == "pay_cryptobot":
        invoice = await PaymentService.create_cryptobot_invoice(amount, user_id)
        if invoice:
            check_callback = f"check_crypto_{invoice['invoice_id']}_{amount}"
    else:
        invoice = await PaymentService.create_xrocket_invoice(amount, user_id)
        if invoice:
            check_callback = f"check_rocket_{invoice['invoice_id']}_{amount}"

    if not invoice:
        back_kb = {
            "inline_keyboard": [[{
                "text": "В профиль",
                "callback_data": "user_profile",
                "icon_custom_emoji_id": "5877536313623711363"
            }]]
        }
        await callback.message.bot(EditCustomMessageMedia(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            media={
                "type": "photo",
                "media": IMG_PROFILE,
                "caption": '<tg-emoji emoji-id="5778527486270770928">❌</tg-emoji> Ошибка при создании счета. Проверь конфигурацию платежной системы или попробуй позже.',
                "parse_mode": "HTML"
            },
            reply_markup=back_kb
        ))
        await state.clear()
        return

    pay_kb = {
        "inline_keyboard": [
            [{"text": "🔗 Оплатить счет", "url": invoice["pay_url"]}],
            [{"text": "🔄 Проверить оплату", "callback_data": check_callback}],
            [{"text": "Отмена", "callback_data": "user_profile", "icon_custom_emoji_id": "5778527486270770928"}]
        ]
    }

    await callback.message.delete()
    await callback.message.bot(SendCustomPhoto(
        chat_id=callback.message.chat.id,
        photo=IMG_PROFILE,
        caption=f"⚠️ <b>Счёт успешно создан!</b>\n\n"
        f"╭ 💰 <b>Сумма к зачислению:</b> <code>${amount}</code>\n"
        f"├ 🪙 <b>Валюта оплаты:</b> <b>USDT</b>\n"
        f"╰ ⏰ <b>Время на оплату:</b> <code>30</code> <b>минут</b>\n\n"
        f"<b>После оплаты нажми кнопку ниже для проверки статуса.</b>",
        parse_mode="HTML",
        reply_markup=pay_kb
    ))
    await state.clear()

@router.callback_query(F.data.startswith("check_crypto_"))
async def check_crypto_pay(callback: CallbackQuery):
    parts = callback.data.split("_")
    invoice_id = parts[2]
    amount = float(parts[3])

    is_paid = await PaymentService.check_cryptobot_invoice(invoice_id)
    if is_paid:
        credited = await database.check_and_mark_invoice_processed(
            invoice_id=invoice_id, payment_system="cryptobot",
            user_id=callback.from_user.id, amount=amount
        )
        if credited:
            logger.info(f"TOP-UP: user={callback.from_user.id} amount=${amount:.2f} system=CryptoBot invoice={invoice_id}")
            await callback.message.delete()
            back_kb = {
                "inline_keyboard": [[{
                    "text": "В главное меню",
                    "callback_data": "user_to_menu",
                    "icon_custom_emoji_id": "5877536313623711363"
                }]]
            }
            await callback.message.bot(SendCustomPhoto(
                chat_id=callback.message.chat.id,
                photo=IMG_PROFILE,
                caption=f"✅ <b>Баланс успешно пополнен на</b> <code>${amount:.2f}</code><b>!</b>",
                parse_mode="HTML",
                reply_markup=back_kb
            ))
        else:
            await callback.answer("ℹ️ Этот платёж уже был зачислен ранее.", show_alert=True)
    else:
        await callback.answer(
            '❌ Оплата не найдена. Если оплатил, подожди пару секунд и нажми еще раз.',
            show_alert=True
        )

@router.callback_query(F.data.startswith("check_rocket_"))
async def check_rocket_pay(callback: CallbackQuery):
    parts = callback.data.split("_")
    invoice_id = parts[2]
    amount = float(parts[3])

    is_paid = await PaymentService.check_xrocket_invoice(invoice_id)
    if is_paid:
        credited = await database.check_and_mark_invoice_processed(
            invoice_id=invoice_id, payment_system="xrocket",
            user_id=callback.from_user.id, amount=amount
        )
        if credited:
            logger.info(f"TOP-UP: user={callback.from_user.id} amount=${amount:.2f} system=xRocket invoice={invoice_id}")
            await callback.message.delete()
            back_kb = {
                "inline_keyboard": [[{
                    "text": "В главное меню",
                    "callback_data": "user_to_menu",
                    "icon_custom_emoji_id": "5877536313623711363"
                }]]
            }
            await callback.message.bot(SendCustomPhoto(
                chat_id=callback.message.chat.id,
                photo=IMG_PROFILE,
                caption=f"✅ <b>Баланс успешно пополнен на</b> <code>${amount:.2f}</code><b>!</b>",
                parse_mode="HTML",
                reply_markup=back_kb
            ))
        else:
            await callback.answer("ℹ️ Этот платёж уже был зачислен ранее.", show_alert=True)
    else:
        await callback.answer(
            '❌ Оплата не найдена.',
            show_alert=True
        )

@router.callback_query(F.data == "user_support")
async def start_user_support(callback: CallbackQuery, state: FSMContext):
    """Начало обращения в поддержку."""
    await state.clear()

    user_id = callback.from_user.id

    if await database.has_open_ticket(user_id):
        back_kb = {
            "inline_keyboard": [[{
                "text": "В главное меню",
                "callback_data": "user_to_menu",
                "icon_custom_emoji_id": "5877536313623711363"
            }]]
        }
        spam_text = "<b>❌ У тебя уже есть открытое обращение. Пожалуйста, ожидай ответа от администратора!</b>"
        if callback.message.photo:
            await callback.message.bot(EditCustomMessageMedia(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                media={"type": "photo", "media": IMG_PROFILE, "caption": spam_text, "parse_mode": "HTML"},
                reply_markup=back_kb
            ))
        else:
            await callback.message.bot(SendCustomMessage(
                chat_id=callback.message.chat.id,
                text=spam_text,
                parse_mode="HTML",
                reply_markup=back_kb
            ))
        await callback.answer()
        return

    await state.set_state(UserSupportState.waiting_for_message)

    cancel_kb = {
        "inline_keyboard": [[{
            "text": "Отмена",
            "callback_data": "user_to_menu",
            "icon_custom_emoji_id": "5778527486270770928"
        }]]
    }

    support_text = (
        "<b><tg-emoji emoji-id=\"5988023995125993550\">💬</tg-emoji> Опиши свою проблему или задай вопрос. "
        "Ты также можешь прикрепить скриншот, если это необходимо:</b>"
    )

    if callback.message.photo:
        await callback.message.bot(EditCustomMessageMedia(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            media={"type": "photo", "media": IMG_PROFILE, "caption": support_text, "parse_mode": "HTML"},
            reply_markup=cancel_kb
        ))
    else:
        await callback.message.bot(SendCustomMessage(
            chat_id=callback.message.chat.id,
            text=support_text,
            parse_mode="HTML",
            reply_markup=cancel_kb
        ))
    await callback.answer()

@router.message(UserSupportState.waiting_for_message)
async def process_user_support_message(message: Message, state: FSMContext):
    """Получение обращения, сохранение в БД и отправка его всем администраторам."""
    await state.clear()

    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

    user_info = await database.get_user_info(user_id)
    if user_info:
        prev_count = user_info.get("support_tickets_count", 0)
        prev_time = user_info.get("last_support_ticket_at")
    else:
        prev_count = 0
        prev_time = None

    tickets_count = prev_count + 1
    display_prev_time = prev_time if prev_time else "Предыдущих обращений не найдено"

    if message.photo:
        media_type = "photo"
        file_id = message.photo[-1].file_id
        message_text = message.caption
    elif message.document:
        media_type = "document"
        file_id = message.document.file_id
        message_text = message.caption
    else:
        media_type = "text"
        file_id = None
        message_text = message.text

    ticket_id = await database.create_support_ticket(
        user_id=user_id,
        username=username,
        message_text=message_text,
        media_type=media_type,
        file_id=file_id
    )

    await database.increment_support_stats(user_id)

    admin_kb = {
        "inline_keyboard": [[
            {"text": "👁 Посмотреть", "callback_data": f"admin_view_ticket_{ticket_id}"}
        ]]
    }

    header = (
        f"<b><tg-emoji emoji-id=\"5988023995125993550\">💬</tg-emoji> Новое обращение в поддержку (Тикет #{ticket_id})!</b>\n\n"
        f"<b>Отправитель:</b> {username} (<code>{user_id}</code>)\n"
        f"<b>Всего обращений:</b> <code>{tickets_count}</code>\n"
        f"<b>Предыдущее обращение:</b> <code>{display_prev_time}</code>\n\n"
    )

    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                caption = header + f"<b>Сообщение:</b>\n<b>{message.caption if message.caption else ''}</b>"
                await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=message.photo[-1].file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=admin_kb
                )
            elif message.document:
                caption = header + f"<b>Сообщение:</b>\n<b>{message.caption if message.caption else ''}</b>"
                await message.bot.send_document(
                    chat_id=admin_id,
                    document=message.document.file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=admin_kb
                )
            else:
                text_content = message.text if message.text else "(без текста)"
                await message.bot.send_message(
                    chat_id=admin_id,
                    text=header + f"<b>Сообщение:</b>\n<b>{text_content}</b>",
                    parse_mode="HTML",
                    reply_markup=admin_kb
                )
        except Exception as e:
            logger.error(f"Error forwarding support message to admin {admin_id}: {e}")

    success_kb = {
        "inline_keyboard": [[{
            "text": "В главное меню",
            "callback_data": "user_to_menu",
            "icon_custom_emoji_id": "5877536313623711363"
        }]]
    }

    await message.bot(SendCustomMessage(
        chat_id=message.chat.id,
        text="<b><tg-emoji emoji-id=\"5951665890079544884\">✅</tg-emoji> Твое обращение успешно отправлено поддержке. Ожидай ответа!</b>",
        parse_mode="HTML",
        reply_markup=success_kb
    ))
