import sys
import traceback
import re
from loguru import logger
from aiogram import Bot
from src.config import config

# --- НАЛАШТУВАННЯ LOGURU ---
logger.remove()

# 1. Вивід в консоль
logger.add(
    sys.stdout, 
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>", 
    level="INFO"
)

# 2. Вивід у файл
logger.add(
    "logs/bot.log", 
    rotation="5 MB", 
    compression="zip", 
    level="DEBUG", 
    encoding="utf-8"
)

class NotifierService:
    def __init__(self):
        self.log_chat_id = config.LOG_CHAT_ID

    def _clean_html(self, text: str) -> str:
        """Видаляє HTML теги для чистого логу в консолі/файлі"""
        clean = re.sub('<[^<]+?>', '', text)
        return clean

    async def info(self, bot: Bot, text: str):
        """
        Звичайний лог (INFO).
        """
        # У файл пишемо чистий текст (без <b>)
        logger.info(self._clean_html(text))
        
        # У Telegram відправляємо красивий (з <b>)
        if self.log_chat_id:
            try:
                await bot.send_message(self.log_chat_id, f"ℹ️ <b>INFO:</b>\n{text}", parse_mode="HTML")
            except Exception as e:
                logger.error(f"Не вдалося відправити лог в ТГ: {e}")

    async def warning(self, bot: Bot, text: str):
        """
        Попередження (WARNING).
        """
        logger.warning(self._clean_html(text))
        
        if self.log_chat_id:
            try:
                await bot.send_message(self.log_chat_id, f"⚠️ <b>WARNING:</b>\n{text}", parse_mode="HTML")
            except: pass

    async def error(self, bot: Bot, text: str, error: Exception = None):
        """
        Критична помилка (ERROR).
        """
        error_text = str(error) if error else "Unknown error"
        tb = traceback.format_exc()
        
        # Логуємо у файл чистий текст, але зберігаємо трейсбек
        clean_msg = self._clean_html(text)
        logger.error(f"{clean_msg} | Error: {error_text}\n{tb}")
        
        if self.log_chat_id:
            try:
                short_tb = tb[-3000:] if len(tb) > 3000 else tb
                msg = (
                    f"🚨 <b>CRITICAL ERROR!</b>\n"
                    f"📝 {text}\n"
                    f"🛑 <b>Error:</b> {error_text}\n\n"
                    f"<code>{short_tb}</code>"
                )
                await bot.send_message(self.log_chat_id, msg, parse_mode="HTML")
            except Exception as e:
                logger.error(f"FATAL: Не вдалося відправити помилку в ТГ: {e}")

notifier = NotifierService()