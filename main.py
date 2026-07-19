import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from config import BOT_TOKEN
from handlers.user import router as user_router
from handlers.admin import router as admin_router
import database
from services.payment import close_http_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def main():
    await database.init_db()
    logger.info("База данных успешно инициализирована.")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(admin_router)
    dp.include_router(user_router)

    logger.info("Запуск Telegram-бота магазина аккаунтов...")
    await bot.delete_webhook(drop_pending_updates=True)

    # polling with auto-restart on connection errors
    while True:
        try:
            await dp.start_polling(bot, handle_signals=False)
            break
        except TelegramUnauthorizedError:
            logger.critical("Неверный токен бота!")
            raise
        except ConnectionError as e:
            logger.warning(f"Ошибка соединения: {e}. Переподключение через 5 секунд...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в polling: {e}. Переподключение через 5 секунд...")
            await asyncio.sleep(5)

async def shutdown():
    """Очистка ресурсов при завершении."""
    await close_http_session()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
    finally:
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(shutdown())
        except Exception:
            pass
