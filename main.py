import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from src.config import config
from src.database.db import db

# Імпортуємо роутери
from src.handlers.common import common_router
from src.handlers.admin import admin_router
from src.handlers.catalog import catalog_router
from src.handlers.cart import cart_router
from src.handlers.analytics import analytics_router # <--- Новий модуль

# Налаштування логування
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    # 1. Підключаємо Redis (для збереження станів при перезапуску)
    redis = Redis.from_url(config.REDIS_DSN)
    storage = RedisStorage(redis=redis)

    # 2. Створюємо бота і диспетчер
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    # 3. Реєструємо роутери (ПОРЯДОК ВАЖЛИВИЙ!)
    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(cart_router)
    dp.include_router(analytics_router) # <--- Підключили аналітику
    dp.include_router(catalog_router)   # Каталог часто ловить все підряд, тому краще в кінці

    # 4. Дії при старті
    @dp.startup.register
    async def on_startup():
        # Підключаємо Postgres
        await db.connect()
        
        # Перевіряємо Redis
        try:
            await redis.ping()
            logging.info("✅ Redis: Успішне підключення!")
        except Exception as e:
            logging.error(f"❌ Redis Error: {e}")

    # 5. Дії при зупинці
    @dp.shutdown.register
    async def on_shutdown():
        await db.disconnect()
        await redis.close()
        logging.info("💤 З'єднання закрито")

    logging.info("🚀 Бот ABC Inventory запускається...")
    
    # Видаляємо старі вебхуки і починаємо слухати
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинений")