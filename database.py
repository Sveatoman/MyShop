import aiosqlite
import time
import os
import string
import random
from typing import List, Dict, Any, Optional
from config import PRICE_INCREMENT_PER_12H

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop.db")

async def init_db():
    """Инициализация базы данных и создание таблиц с поддержкой автомиграции."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")

        db.row_factory = aiosqlite.Row
        migrate = False
        try:
            async with db.execute("PRAGMA table_info(users)") as cursor:
                columns = [row["name"] for row in await cursor.fetchall()]
                if columns and "first_name" not in columns:
                    migrate = True
        except Exception:
            pass

        if migrate:

            await db.execute("DROP TABLE IF EXISTS accounts")
            await db.execute("DROP TABLE IF EXISTS services")
            await db.execute("DROP TABLE IF EXISTS users")
            await db.execute("DROP TABLE IF EXISTS orders")
            await db.commit()

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                registered_at INTEGER NOT NULL,
                balance REAL NOT NULL DEFAULT 0.0,
                support_tickets_count INTEGER NOT NULL DEFAULT 0,
                last_support_ticket_at TEXT DEFAULT NULL
            )
        """)

        try:
            async with db.execute("PRAGMA table_info(users)") as cursor:
                columns = [row["name"] for row in await cursor.fetchall()]
                if columns and "support_tickets_count" not in columns:
                    await db.execute("ALTER TABLE users ADD COLUMN support_tickets_count INTEGER NOT NULL DEFAULT 0")
                    await db.execute("ALTER TABLE users ADD COLUMN last_support_ticket_at TEXT DEFAULT NULL")
                    await db.commit()
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                base_price REAL NOT NULL,
                type TEXT NOT NULL DEFAULT 'text'
            )
        """)

        try:
            async with db.execute("PRAGMA table_info(services)") as cursor:
                columns = [row["name"] for row in await cursor.fetchall()]
                if columns and "type" not in columns:
                    await db.execute("ALTER TABLE services ADD COLUMN type TEXT NOT NULL DEFAULT 'text'")
                    await db.commit()
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                credentials TEXT NOT NULL,
                added_at INTEGER NOT NULL,
                is_sold INTEGER NOT NULL DEFAULT 0,
                sold_price REAL DEFAULT NULL,
                FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                total_price REAL NOT NULL,
                purchased_at INTEGER NOT NULL,
                delivered_data TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS processed_invoices (
                invoice_id TEXT PRIMARY KEY,
                payment_system TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                processed_at INTEGER NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                amount REAL NOT NULL,
                max_activations INTEGER NOT NULL,
                current_activations INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                promo_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                activated_at INTEGER NOT NULL,
                FOREIGN KEY (promo_id) REFERENCES promocodes(id) ON DELETE CASCADE,
                UNIQUE(promo_id, user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                message_text TEXT,
                media_type TEXT NOT NULL,
                file_id TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                reply_text TEXT,
                replied_at TEXT
            )
        """)

        async with db.execute("PRAGMA table_info(support_tickets)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if "reply_text" not in columns:
                await db.execute("ALTER TABLE support_tickets ADD COLUMN reply_text TEXT;")
            if "replied_at" not in columns:
                await db.execute("ALTER TABLE support_tickets ADD COLUMN replied_at TEXT;")

        await db.commit()

async def add_user(user_id: int, username: Optional[str], first_name: str):
    """Добавляет или обновляет пользователя в БД при команде /start."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, registered_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        """, (user_id, username, first_name, int(time.time())))
        await db.commit()

async def get_user_info(user_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает информацию о пользователе."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_user_purchases_count(user_id: int) -> int:
    """Возвращает общее число купленных аккаунтов пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT SUM(quantity) FROM orders WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] is not None else 0

async def get_user_orders(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Возвращает список последних заказов пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY purchased_at DESC LIMIT ?",
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_order_by_id(order_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает данные заказа по его ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def create_order(user_id: int, service_name: str, category: str, quantity: int, total_price: float, delivered_data: str):
    """Создает запись о заказе в БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO orders (user_id, service_name, category, quantity, total_price, purchased_at, delivered_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, service_name, category, quantity, total_price, int(time.time()), delivered_data))
        await db.commit()

async def add_user_balance(user_id: int, amount: float):
    """Начисление средств на баланс пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = round(balance + ?, 2) WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()

async def check_and_mark_invoice_processed(invoice_id: str, payment_system: str, user_id: int, amount: float) -> bool:
    """Проверяет, был ли инвойс уже обработан. Если нет — помечает и возвращает True.
    Если инвойс уже был обработан ранее — возвращает False (зачислять повторно нельзя)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT invoice_id FROM processed_invoices WHERE invoice_id = ?",
            (invoice_id,)
        ) as cursor:
            if await cursor.fetchone():
                return False

        await db.execute(
            "INSERT INTO processed_invoices (invoice_id, payment_system, user_id, amount, processed_at) VALUES (?, ?, ?, ?, ?)",
            (invoice_id, payment_system, user_id, amount, int(time.time()))
        )
        await db.execute(
            "UPDATE users SET balance = round(balance + ?, 2) WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()
        return True

async def sell_accounts_and_create_order(
    user_id: int, service_name: str, category_name: str,
    quantity: int, total_price: float,
    account_ids: List[int], credentials_text: str
):
    """Проводит транзакцию покупки: списывает баланс (в $), помечает аккаунты проданными и создает заказ."""
    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute("BEGIN TRANSACTION;")
        try:
            placeholders = ",".join("?" for _ in account_ids)

            async with db.execute(
                f"SELECT COUNT(*) FROM accounts WHERE id IN ({placeholders}) AND is_sold = 0",
                account_ids
            ) as cursor:
                row = await cursor.fetchone()
                unsold_count = row[0] if row else 0

            if unsold_count != len(account_ids):
                raise ValueError("Some accounts are already sold")

            async with db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                current_balance = row[0] if row else 0.0

            current_balance = round(current_balance, 2)
            total_price = round(total_price, 2)

            if current_balance < total_price:
                raise ValueError("Insufficient balance")

            await db.execute(
                "UPDATE users SET balance = round(balance - ?, 2) WHERE user_id = ?",
                (total_price, user_id)
            )

            price_per_unit = total_price / quantity
            await db.execute(
                f"UPDATE accounts SET is_sold = 1, sold_price = ? WHERE id IN ({placeholders})",
                [price_per_unit] + account_ids
            )

            await db.execute("""
                INSERT INTO orders (user_id, service_name, category, quantity, total_price, purchased_at, delivered_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, service_name, category_name, quantity, total_price, int(time.time()), credentials_text))

            await db.commit()
        except Exception as e:
            await db.execute("ROLLBACK;")
            raise e

async def get_services() -> List[Dict[str, Any]]:
    """Возвращает список всех сервисов."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM services ORDER BY name ASC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_service_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Возвращает сервис по имени."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM services WHERE LOWER(name) = LOWER(?)", (name,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_service_by_id(service_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает сервис по ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM services WHERE id = ?", (service_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def create_service(name: str, base_price: float, service_type: str = 'text') -> int:
    """Создает новый сервис с указанным типом (text или file)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO services (name, base_price, type) VALUES (?, ?, ?)",
            (name.strip(), base_price, service_type)
        )
        await db.commit()
        return cursor.lastrowid

async def update_service_price(service_id: int, new_price: float):
    """Обновляет базовую цену."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET base_price = ? WHERE id = ?",
            (new_price, service_id)
        )
        await db.commit()

async def delete_service(service_id: int):
    """Удаляет сервис и все его непроданные/проданные аккаунты."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("DELETE FROM services WHERE id = ?", (service_id,))
        await db.commit()

async def add_accounts(service_id: int, credentials_list: List[str]):
    """Добавляет аккаунты."""
    current_time = int(time.time())
    data = [(service_id, cred.strip(), current_time) for cred in credentials_list if cred.strip()]
    if not data:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT INTO accounts (service_id, credentials, added_at) VALUES (?, ?, ?)",
            data
        )
        await db.commit()

async def get_available_accounts(service_id: int) -> List[Dict[str, Any]]:
    """Возвращает доступные к продаже аккаунты сервиса."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE service_id = ? AND is_sold = 0 ORDER BY added_at ASC",
            (service_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_available_accounts_count(service_id: int) -> int:
    """Возвращает количество свободных аккаунтов сервиса."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM accounts WHERE service_id = ? AND is_sold = 0",
            (service_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_stats() -> Dict[str, Any]:
    """Возвращает статистику для админ-панели."""
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}

        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            stats["users_count"] = row[0] if row else 0

        async with db.execute("SELECT COUNT(*) FROM accounts WHERE is_sold = 0") as cursor:
            row = await cursor.fetchone()
            stats["available_count"] = row[0] if row else 0

        async with db.execute("SELECT COALESCE(SUM(balance), 0) FROM users") as cursor:
            row = await cursor.fetchone()
            stats["total_balance"] = row[0] if row else 0.0

        async with db.execute("SELECT COALESCE(SUM(quantity), 0) FROM orders") as cursor:
            row = await cursor.fetchone()
            stats["sold_count"] = row[0] if row else 0

        async with db.execute("SELECT COALESCE(SUM(total_price), 0) FROM orders") as cursor:
            row = await cursor.fetchone()
            stats["sold_amount"] = row[0] if row else 0.0

        async with db.execute("SELECT COUNT(*) FROM promocodes WHERE current_activations < max_activations") as cursor:
            row = await cursor.fetchone()
            stats["active_promos_count"] = row[0] if row else 0

        async with db.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'") as cursor:
            row = await cursor.fetchone()
            stats["open_tickets_count"] = row[0] if row else 0

        import datetime
        tz_msk = datetime.timezone(datetime.timedelta(hours=3))
        now_msk = datetime.datetime.now(tz_msk)

        today_start_msk = datetime.datetime(now_msk.year, now_msk.month, now_msk.day, tzinfo=tz_msk)
        today_start_ts = int(today_start_msk.timestamp())

        yesterday_start_ts = today_start_ts - 86400

        thirty_days_ago_ts = int(now_msk.timestamp()) - (30 * 86400)

        async with db.execute(
            "SELECT COALESCE(SUM(quantity), 0), COALESCE(SUM(total_price), 0.0) FROM orders WHERE purchased_at >= ?",
            (today_start_ts,)
        ) as cursor:
            row = await cursor.fetchone()
            stats["today_sold_count"] = row[0] if row else 0
            stats["today_sold_amount"] = row[1] if row else 0.0

        async with db.execute(
            "SELECT COALESCE(SUM(quantity), 0), COALESCE(SUM(total_price), 0.0) FROM orders WHERE purchased_at >= ? AND purchased_at < ?",
            (yesterday_start_ts, today_start_ts)
        ) as cursor:
            row = await cursor.fetchone()
            stats["yesterday_sold_count"] = row[0] if row else 0
            stats["yesterday_sold_amount"] = row[1] if row else 0.0

        async with db.execute(
            "SELECT COALESCE(SUM(quantity), 0), COALESCE(SUM(total_price), 0.0) FROM orders WHERE purchased_at >= ?",
            (thirty_days_ago_ts,)
        ) as cursor:
            row = await cursor.fetchone()
            stats["month_sold_count"] = row[0] if row else 0
            stats["month_sold_amount"] = row[1] if row else 0.0

        return stats

async def age_accounts_by_12_hours():
    """Состаривает все непроданные аккаунты на 12 часов (для отладки)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE accounts SET added_at = added_at - (12 * 3600) WHERE is_sold = 0")
        await db.commit()

def group_accounts_by_category(base_price: float, accounts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Группирует аккаунты по категориям отлёжки и вычисляет динамическую цену."""
    categories = {}
    current_time = int(time.time())

    for acc in accounts:
        added_at = acc["added_at"]
        hours_passed = (current_time - added_at) / 3600.0
        step = int(hours_passed // 12)

        if step == 0:
            category_name = "Свежие"
        else:
            category_name = f"{step * 12}ч+"

        price = base_price + step * PRICE_INCREMENT_PER_12H

        if category_name not in categories:
            categories[category_name] = {
                "price": price,
                "accounts": []
            }
        categories[category_name]["accounts"].append(acc)

    return categories

def generate_promo_code(length: int = 8) -> str:
    """Генерирует рандомный промокод из букв и цифр."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

async def create_promocode(amount: float, max_activations: int) -> str:
    """Создает промокод и возвращает сгенерированный код."""
    code = generate_promo_code()
    async with aiosqlite.connect(DB_PATH) as db:

        for _ in range(5):
            try:
                await db.execute(
                    "INSERT INTO promocodes (code, amount, max_activations, created_at) VALUES (?, ?, ?, ?)",
                    (code, amount, max_activations, int(time.time()))
                )
                await db.commit()
                return code
            except aiosqlite.IntegrityError:
                code = generate_promo_code()
        raise ValueError("Could not generate unique promo code")

async def get_promocode_by_code(code: str) -> Optional[Dict[str, Any]]:
    """Возвращает промокод по коду."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM promocodes WHERE UPPER(code) = UPPER(?)", (code,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def activate_promocode(code: str, user_id: int) -> dict:
    """Активирует промокод для пользователя.
    Возвращает dict с ключами: success (bool), message (str), amount (float|None).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT * FROM promocodes WHERE UPPER(code) = UPPER(?)", (code,)
        ) as cursor:
            promo = await cursor.fetchone()

        if not promo:
            return {"success": False, "message": "Промокод не найден.", "amount": None}

        promo = dict(promo)

        if promo["current_activations"] >= promo["max_activations"]:
            return {"success": False, "message": "Промокод уже исчерпан (все активации использованы).", "amount": None}

        async with db.execute(
            "SELECT id FROM promo_activations WHERE promo_id = ? AND user_id = ?",
            (promo["id"], user_id)
        ) as cursor:
            if await cursor.fetchone():
                return {"success": False, "message": "Ты уже активировал этот промокод.", "amount": None}

        await db.execute(
            "INSERT INTO promo_activations (promo_id, user_id, activated_at) VALUES (?, ?, ?)",
            (promo["id"], user_id, int(time.time()))
        )
        await db.execute(
            "UPDATE promocodes SET current_activations = current_activations + 1 WHERE id = ?",
            (promo["id"],)
        )
        await db.execute(
            "UPDATE users SET balance = round(balance + ?, 2) WHERE user_id = ?",
            (promo["amount"], user_id)
        )
        await db.commit()

        return {"success": True, "message": "Промокод успешно активирован!", "amount": promo["amount"]}

async def get_all_promocodes() -> List[Dict[str, Any]]:
    """Возвращает список всех промокодов."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM promocodes ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def delete_promocode(promo_id: int):
    """Удаляет промокод."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("DELETE FROM promocodes WHERE id = ?", (promo_id,))
        await db.commit()

async def get_all_user_ids() -> List[int]:
    """Возвращает список user_id всех зарегистрированных пользователей."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def increment_support_stats(user_id: int):
    """Увеличивает счетчик обращений в поддержку и обновляет дату последнего обращения по МСК."""
    import datetime
    tz_msk = datetime.timezone(datetime.timedelta(hours=3))
    now_msk = datetime.datetime.now(tz_msk)
    date_str = now_msk.strftime("%d.%m.%Y %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET support_tickets_count = support_tickets_count + 1,
                last_support_ticket_at = ?
            WHERE user_id = ?
        """, (date_str, user_id))
        await db.commit()

async def has_open_ticket(user_id: int) -> bool:
    """Проверяет, есть ли у пользователя открытые тикеты в поддержку."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM support_tickets WHERE user_id = ? AND status = 'open' LIMIT 1",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None

async def create_support_ticket(user_id: int, username: Optional[str], message_text: Optional[str], media_type: str, file_id: Optional[str]) -> int:
    """Создает новое обращение в поддержку и возвращает его ID."""
    import datetime
    tz_msk = datetime.timezone(datetime.timedelta(hours=3))
    now_msk = datetime.datetime.now(tz_msk)
    date_str = now_msk.strftime("%d.%m.%Y %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO support_tickets (user_id, username, message_text, media_type, file_id, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'open')
        """, (user_id, username, message_text, media_type, file_id, date_str))
        ticket_id = cursor.lastrowid
        await db.commit()
        return ticket_id

async def get_open_tickets() -> List[Dict[str, Any]]:
    """Возвращает список всех открытых (неотвеченных) обращений."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM support_tickets WHERE status = 'open' ORDER BY id ASC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_ticket_by_id(ticket_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает детальную информацию о тикете по его ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM support_tickets WHERE id = ?",
            (ticket_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def update_ticket_status(ticket_id: int, status: str):
    """Обновляет статус тикета в БД."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE support_tickets SET status = ? WHERE id = ?",
            (status, ticket_id)
        )
        await db.commit()

async def save_ticket_reply(ticket_id: int, reply_text: str):
    """Сохраняет ответ администратора, дату ответа по МСК и меняет статус на replied."""
    import datetime
    tz_msk = datetime.timezone(datetime.timedelta(hours=3))
    now_msk = datetime.datetime.now(tz_msk)
    replied_at = now_msk.strftime("%d.%m.%Y %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE support_tickets
            SET status = 'replied',
                reply_text = ?,
                replied_at = ?
            WHERE id = ?
        """, (reply_text, replied_at, ticket_id))
        await db.commit()

async def get_user_tickets_history(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Возвращает историю последних N тикетов пользователя (включая ответы)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM support_tickets
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Возвращает информацию о пользователе по его username."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
            (username.strip().lstrip("@"),)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_user_purchases_count(user_id: int) -> int:
    """Возвращает общее количество купленных аккаунтов пользователем."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM orders WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_user_purchases_history(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Возвращает историю последних N покупок пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM orders
            WHERE user_id = ?
            ORDER BY purchased_at DESC
            LIMIT ?
        """, (user_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
