from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from loguru import logger


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Дані про юзера
        user = data.get("event_from_user")
        user_id = user.id if user else "Unknown"
        username = f"@{user.username}" if user and user.username else ""
        
        # Логуємо повідомлення
        if isinstance(event, Message) and event.text:
            logger.info(f"✉️ MSG | {user_id} {username} | Text: '{event.text}'")
            
        # Логуємо натискання кнопок
        elif isinstance(event, CallbackQuery):
            logger.info(f"🔘 CLB | {user_id} {username} | Data: '{event.data}'")

        # Передаємо управління далі
        return await handler(event, data)