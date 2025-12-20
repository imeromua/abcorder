from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu(role: str = 'user') -> ReplyKeyboardMarkup:
    """
    Головне меню (Reply кнопки).
    Адаптується під роль користувача.
    """
    # 1. Базовий ряд (доступний всім)
    kb = [
        [KeyboardButton(text="📂 Каталог"), KeyboardButton(text="🛒 Кошик")]
    ]

    # 2. Ряд для Магазинів та Адмінів (Аналітика)
    # Звичайний юзер цього не бачить
    if role in ['shop', 'admin', 'patron']:
         kb.append([KeyboardButton(text="📊 Аналітика / Автозамовлення")])

    # 3. Ряд Адміністратора
    if role == 'admin':
        kb.append([KeyboardButton(text="⚙️ Адмінка")])

    return ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,       # Робить кнопки компактними
        persistent=True,            # Меню не ховається саме по собі
        input_field_placeholder="Оберіть пункт меню..." # Підказка в полі вводу
    )