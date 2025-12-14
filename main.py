import asyncio
import signal  # <--- Додаємо
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from src.config import config
from src.database.db import db
from src.handlers.admin import admin_router
from src.handlers.analytics import analytics_router
from src.handlers.cart import cart_router
from src.handlers.catalog import catalog_router
from src.handlers.common import common_router
from src.middlewares.logger import LoggingMiddleware
from src.services.notifier import logger, notifier


# Функція для ігнорування Ctrl+C
def signal_handler(sig, frame):
    logger.info("🛑 Ctrl+C натиснуто, але я працюю далі! (Щоб зупинити: 'kill <pid>' або закрий термінал)")

async def main():
    # Реєструємо ігнорування SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)

    redis = Redis.from_url(config.REDIS_DSN)
    storage = RedisStorage(redis=redis)
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    dp.update.middleware(LoggingMiddleware())

    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(cart_router)
    dp.include_router(analytics_router)
    dp.include_router(catalog_router)

    @dp.startup.register
    async def on_startup():
        await db.connect()
        try:
            await redis.ping()
            logger.info("Redis connected successfully")
        except Exception:
            logger.error("Redis connection failed")
        await notifier.info(bot, "🚀 <b>Бот успішно запущено!</b>")

    @dp.shutdown.register
    async def on_shutdown():
        await db.disconnect()
        await redis.close()
        await notifier.warning(bot, "💤 <b>Бот зупиняється...</b>")

    logger.info("Starting bot polling... (Ctrl+C disabled)")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass # Цей блок тепер майже не спрацює, бо ми перехопили сигнал вище