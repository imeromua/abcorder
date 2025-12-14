import logging
import asyncpg
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
            # 🔥 АВТОМАТИЧНЕ СТВОРЕННЯ ТАБЛИЦЬ ПРИ СТАРТІ 🔥
            await self.create_tables()
        except Exception as e:
            logging.error(f"❌ Помилка БД: {e}")
            raise e

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def create_tables(self):
        """Створює необхідну структуру БД, якщо її немає"""
        queries = [
            # 1. Таблиця користувачів
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                role VARCHAR(20) DEFAULT 'shop',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # 2. Таблиця товарів
            """
            CREATE TABLE IF NOT EXISTS products (
                article VARCHAR(50) PRIMARY KEY,
                name TEXT,
                department INTEGER,
                category_path TEXT,
                supplier TEXT,
                resident TEXT,
                cluster VARCHAR(10),
                sales_qty REAL DEFAULT 0,
                sales_sum REAL DEFAULT 0,
                stock_qty REAL DEFAULT 0,
                stock_sum REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # 3. Таблиця кошика
            """
            CREATE TABLE IF NOT EXISTS cart (
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                article VARCHAR(50) REFERENCES products(article) ON DELETE CASCADE,
                quantity INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, article)
            );
            """
        ]
        
        async with self.pool.acquire() as connection:
            for q in queries:
                await connection.execute(q)
        logging.info("📦 Структура таблиць перевірена/створена.")

    # --- Методи для запитів ---
    async def execute(self, query, *args):
        async with self.pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def fetch_one(self, query, *args):
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetch_all(self, query, *args):
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)

db = Database()