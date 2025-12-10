from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

def build_catalog_menu(items: list, level: str, parent_id: str = ""):
    """
    Генерує кнопки для навігації.
    items: список рядків АБО словників
    """
    builder = InlineKeyboardBuilder()

    for item in items:
        if isinstance(item, dict):
            # Варіант 1: Це ТОВАР (є ціна)
            if 'price' in item:
                text = f"{item['name']} | {item['price']:.0f} грн"
                callback = f"prod_{item['article']}"
            # Варіант 2: Це ГРУПА з довгим іменем (є id і name)
            else:
                text = item['name']
                # callback буде коротким: cat_group_10_1
                callback = f"cat_{level}_{item['id']}"
            
            builder.button(text=text, callback_data=callback)
        else:
            # Варіант 3: Просто рядок (наприклад, Відділ "10")
            text = str(item)
            callback = f"cat_{level}_{item}" 
            builder.button(text=text, callback_data=callback)

    # Сітка
    if level == 'products':
        builder.adjust(1)
    else:
        builder.adjust(2)

    # Кнопки НАЗАД
    if level == 'dept':
        builder.row(InlineKeyboardButton(text="❌ Закрити", callback_data="close_catalog"))
    elif level == 'group':
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="open_catalog_root"))
    elif level == 'subgroup':
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_dept_{parent_id}"))
    elif level == 'products':
        # Якщо ми в товарах, то "Назад" веде до списку груп цього відділу
        # parent_id тут має бути номером відділу
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_dept_{parent_id}"))

    return builder.as_markup()