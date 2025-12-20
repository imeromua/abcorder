import os
from dotenv import load_dotenv
from loguru import logger

# Завантажуємо змінні середовища
load_dotenv()

class Config:
    # --- TELEGRAM ---
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Парсинг списку адмінів: "123, 456" -> [123, 456]
    ADMIN_IDS = [
        int(x) for x in os.getenv("ADMIN_IDS", "").split(",") 
        if x.strip().isdigit()
    ]
    
    # ID чату/групи для технічних логів (може бути пустим)
    LOG_CHAT_ID = os.getenv("LOG_CHAT_ID")

    # --- DATABASE (PostgreSQL) ---
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASS = os.getenv("DB_PASS", "postgres")
    DB_NAME = os.getenv("DB_NAME", "abc_bot_db")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")

    # --- REDIS (Cache & FSM) ---
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = os.getenv("REDIS_PORT", "6379")

    # Рядки підключення (DSN)
    POSTGRES_DSN = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    REDIS_DSN = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

    # --- БІЗНЕС-ЛОГІКА ---
    # Незгораний залишок для магазинів
    STOCK_RESERVE = int(os.getenv("STOCK_RESERVE", 3))
    
    # Фільтри імпорту (ігнорувати товари, де продажі І залишок менші за ці числа)
    MIN_SALES = int(os.getenv("MIN_SALES_THRESHOLD", 0))
    MIN_STOCK = int(os.getenv("MIN_STOCK_THRESHOLD", 0))
    
    # Максимальна кількість товару в одному рядку замовлення (захист від дурня)
    MAX_ORDER_QTY = int(os.getenv("MAX_ORDER_QUANTITY", 1000))

    def log_config(self):
        """Виводить поточну конфігурацію в лог, маскуючи секретні дані"""
        # Маскуємо токен
        token = self.BOT_TOKEN
        masked_token = f"{token[:5]}...{token[-5:]}" if token and len(token) > 10 else "******"
        
        # Маскуємо пароль БД
        masked_pass = "******" if self.DB_PASS else "None"

        logger.info("===== 🛠 CONFIGURATION LOADED 🛠 =====")
        logger.info(f"🤖 BOT_TOKEN: {masked_token}")
        logger.info(f"👑 ADMIN_IDS: {self.ADMIN_IDS}")
        logger.info(f"🐘 DB: {self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME} (User: {self.DB_USER})")
        logger.info(f"🧠 REDIS: {self.REDIS_HOST}:{self.REDIS_PORT}")
        logger.info(f"📊 FILTERS: Sales >= {self.MIN_SALES} OR Stock >= {self.MIN_STOCK}")
        logger.info(f"📦 RULES: Reserve={self.STOCK_RESERVE} | MaxQty={self.MAX_ORDER_QTY}")
        logger.info("========================================")

# Створюємо глобальний екземпляр
config = Config()