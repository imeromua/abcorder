from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from src.config import config

def get_main_menu(user_id: int):
    """Головне меню (нижня клавіатура)"""
    
    # Базові кнопки для всіх
    kb = [
        [KeyboardButton(text="📂 Каталог"), KeyboardButton(text="🛒 Кошик")],
        [KeyboardButton(text="👤 Мій профіль")] # Аналітику додамо пізніше
    ]

    # Додаємо Адмінку ТІЛЬКИ для обраних
    if user_id in config.ADMIN_IDS:
        kb.append([KeyboardButton(text="⚙️ Адмінка")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)