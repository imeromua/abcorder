import asyncpg
import logging
from src.config import config

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Відкриваємо з'єднання при старті"""
        try:
            self.pool = await asyncpg.create_pool(
                dsn=config.POSTGRES_DSN,
                min_size=1,
                max_size=10
            )
            logging.info("✅ Успішне підключення до PostgreSQL")
        except Exception as e:
            logging.error(f"❌ Помилка БД: {e}")
            raise e

    async def disconnect(self):
        """Закриваємо з'єднання"""
        if self.pool:
            await self.pool.close()

    # --- Методи для запитів ---
    async def execute(self, query, *args):
        """Для INSERT, UPDATE, DELETE"""
        async with self.pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def fetch_one(self, query, *args):
        """Отримати один рядок"""
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetch_all(self, query, *args):
        """Отримати список"""
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)

db = Database()