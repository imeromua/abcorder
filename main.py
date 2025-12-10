import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from src.config import config
from src.database.db import db
from src.handlers.admin import admin_router
from src.handlers.cart import cart_router
from src.handlers.catalog import catalog_router
from src.handlers.common import common_router

# Налаштування логування
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    # 1. Створюємо бота і диспетчер
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    # 2. Реєструємо роутери (наші хендлери)
    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(cart_router)
    dp.include_router(catalog_router)

    # 3. Дії при старті (підключення до БД)
    # Використовуємо startup хук
    @dp.startup.register
    async def on_startup():
        await db.connect()

    # 4. Дії при зупинці
    @dp.shutdown.register
    async def on_shutdown():
        await db.disconnect()

    logging.info("🚀 Бот ABC Inventory запускається...")
    
    # Видаляємо старі вебхуки і починаємо слухати
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинений")