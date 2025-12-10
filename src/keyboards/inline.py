from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_product_keyboard(article: str, back_callback: str = None):
    """
    Кнопки під карткою товару.
    back_callback: куди повертатися (зберігаємо його і для кнопки Додати)
    """
    # Якщо back_callback є, додаємо його до callback_data кнопки додавання
    # Формат: add_АРТИКУЛ_BACKLINK
    if back_callback:
        add_callback = f"add_{article}_{back_callback}"
    else:
        add_callback = f"add_{article}"

    buttons = [
        [InlineKeyboardButton(text="📥 Додати в замовлення", callback_data=add_callback)]
    ]
    
    # Кнопка Назад/Закрити
    if back_callback:
        buttons.append([InlineKeyboardButton(text="⬅️ Назад до списку", callback_data=back_callback)])
    else:
        buttons.append([InlineKeyboardButton(text="❌ Закрити картку", callback_data="close_catalog")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cart_keyboard(article: str):
    """Кнопки під час введення кількості"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_order")]
    ])
    return keyboard

def get_success_add_keyboard(back_callback: str = None):
    """Кнопки після успішного додавання"""
    buttons = [
        [InlineKeyboardButton(text="🛒 Перейти до кошика", callback_data="view_cart_btn")]
    ]
    
    # Якщо є куди повертатися - додаємо кнопку "Продовжити"
    if back_callback and back_callback != "None":
        buttons.append([InlineKeyboardButton(text="⬅️ Продовжити покупки", callback_data=back_callback)])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cart_actions_keyboard():
    """Кнопки під кошиком"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сформувати замовлення", callback_data="submit_order")
        ],
        [
            InlineKeyboardButton(text="🗑 Очистити все", callback_data="clear_cart")
        ]
    ])
    return keyboard