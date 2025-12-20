import asyncpg
from loguru import logger
from src.config import config

class Database:
    def __init__(self):
        self.pool: asyncpg.Pool = None

    async def connect(self):
        """Відкриваємо з'єднання при старті з налаштуванням пулу"""
        try:
            logger.info(f"🔌 Connecting to PostgreSQL at {config.DB_HOST}:{config.DB_PORT}...")
            
            # Створюємо пул з'єднань
            self.pool = await asyncpg.create_pool(
                dsn=config.POSTGRES_DSN,
                min_size=5,
                max_size=50
            )
            
            logger.info(f"✅ DB Connection established. Pool size: {self.pool.get_min_size()}-{self.pool.get_max_size()}")
            
            # Перевірка та створення таблиць
            await self.create_tables()
            
        except Exception as e:
            logger.critical(f"❌ Database Connection Failed: {e}")
            raise e

    async def disconnect(self):
        """Закриваємо з'єднання при зупинці"""
        if self.pool:
            await self.pool.close()
            logger.info("💤 DB Connection closed.")

    async def create_tables(self):
        """Створює та оновлює структуру БД"""
        logger.info("🛠 Checking database schema...")
        
        # 1. Створення таблиць (якщо їх немає)
        create_queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                role VARCHAR(20) DEFAULT 'shop',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
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
        
        # 2. Міграції (додавання колонок у вже існуючі таблиці)
        # Використовуємо IF NOT EXISTS, щоб не було помилок
        migration_queries = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'shop';",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS cluster VARCHAR(10);"
        ]
        
        async with self.pool.acquire() as connection:
            # Створення
            for q in create_queries:
                await connection.execute(q)
            
            # Міграція
            for q in migration_queries:
                try:
                    await connection.execute(q)
                except Exception as e:
                    logger.warning(f"Migration warning: {e}")
        
        logger.info("📦 DB Schema verified/updated successfully.")

    # --- Методи для простих запитів (Auto-commit) ---
    
    async def execute(self, query, *args):
        """Виконання запиту без повернення результату"""
        async with self.pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def fetch_one(self, query, *args):
        """Отримання одного рядка"""
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetch_all(self, query, *args):
        """Отримання списку рядків"""
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)

# Глобальний екземпляр бази
db = Database()