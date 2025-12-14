from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_menu(role: str):
    """
    Генерує меню залежно від ролі користувача з БД.
    role: 'shop', 'patron', 'admin'
    """
    # 1. Базові кнопки (для всіх)
    kb = [
        [KeyboardButton(text="📂 Каталог"), KeyboardButton(text="🛒 Кошик")],
        [KeyboardButton(text="👤 Мій профіль")]
    ]

    # 2. Кнопки для Патрона (Аналітика)
    if role in ['patron', 'admin']:
        kb.insert(1, [KeyboardButton(text="📊 Аналітика / Автозамовлення")])

    # 3. Кнопки для Адміна
    if role == 'admin':
        kb.append([KeyboardButton(text="⚙️ Адмінка")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)