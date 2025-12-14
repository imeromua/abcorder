import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from src.config import config
from src.database.db import db
from src.services.notifier import logger, notifier

# Імпорт роутерів (обробників команд)
from src.handlers.common import common_router
from src.handlers.admin import admin_router
from src.handlers.catalog import catalog_router
from src.handlers.cart import cart_router
from src.handlers.analytics import analytics_router

async def main():
    # 1. Налаштування Redis (Кеш та FSM)
    redis = Redis.from_url(config.REDIS_DSN)
    storage = RedisStorage(redis=redis)

    # 2. Ініціалізація бота
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    # 3. Реєстрація роутерів (порядок важливий!)
    dp.include_router(common_router)     # /start, /help
    dp.include_router(admin_router)      # Адмінка
    dp.include_router(cart_router)       # Кошик та замовлення
    dp.include_router(catalog_router)    # Пошук та каталог
    dp.include_router(analytics_router)  # Звіти та аналітика

    # 4. Хук при старті (On Startup)
    @dp.startup.register
    async def on_startup():
        # Підключення до БД
        await db.connect()
        
        # Перевірка Redis
        try:
            await redis.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")

        # Сповіщення в адмін-чат (через наш сервіс notifier)
        await notifier.info(bot, "🚀 <b>Бот успішно запущено!</b>\nСистеми в нормі, готовий до роботи.")

    # 5. Хук при зупинці (On Shutdown)
    @dp.shutdown.register
    async def on_shutdown():
        await db.disconnect()
        await redis.close()
        await notifier.warning(bot, "💤 <b>Бот зупиняється...</b> (Signal received)")

    # 6. Запуск
    logger.info("Starting bot polling...")
    
    # Видаляємо старі повідомлення, які накопичилися поки бот спав
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Погнали!
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        # Windows fix для asyncio (іноді потрібен)
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
        asyncio.run(main())
    except KeyboardInterrupt:
        # Тихо виходимо при натисканні Ctrl+C
        pass
    except Exception as e:
        logger.exception(f"Critical Error in main: {e}")