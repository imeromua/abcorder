import os
from dotenv import load_dotenv

# Завантажуємо змінні середовища з файлу .env
load_dotenv()

class Config:
    # --- TELEGRAM ---
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Перетворюємо рядок "123,456" у список чисел [123, 456]
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
    
    # ID групи для логів та аудитів (може бути None, якщо не налаштовано)
    LOG_CHAT_ID = os.getenv("LOG_CHAT_ID")

    # --- DATABASE (PostgreSQL) ---
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASS")
    DB_NAME = os.getenv("DB_NAME")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")

    # --- REDIS (Кеш та стани FSM) ---
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = os.getenv("REDIS_PORT")

    # Формування рядків підключення (DSN)
    POSTGRES_DSN = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    REDIS_DSN = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

    # --- БІЗНЕС-ЛОГІКА ---
    
    # Незгораний залишок для магазинів (менше цього числа товар недоступний для замовлення)
    # Якщо в .env немає змінної, використовуємо 3 за замовчуванням
    STOCK_RESERVE = int(os.getenv("STOCK_RESERVE", 3))

    # Фільтри імпорту (відсіювання "мертвих" товарів)
    # Товар не потрапить в базу, якщо: Sales < X  AND  Stock < Y
    MIN_SALES = int(os.getenv("MIN_SALES_THRESHOLD", 0))
    MIN_STOCK = int(os.getenv("MIN_STOCK_THRESHOLD", 0))

    # Максимальна кількість товару в одній позиції
    MAX_ORDER_QTY = int(os.getenv("MAX_ORDER_QUANTITY", 1000))

# Створюємо екземпляр, щоб імпортувати його як `from src.config import config`
config = Config()