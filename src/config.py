import os

from dotenv import load_dotenv

# Завантажуємо змінні з .env
load_dotenv()

class Config:
    # Телеграм
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    # Перетворюємо рядок "123,456" у список чисел [123, 456]
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

    # База даних
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASS")
    DB_NAME = os.getenv("DB_NAME")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")

    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = os.getenv("REDIS_PORT")

    # Рядок підключення для asyncpg
    POSTGRES_DSN = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    # Рядок для Redis
    REDIS_DSN = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

config = Config()