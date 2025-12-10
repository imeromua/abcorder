from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_product_keyboard(article: str):
    """Кнопки під карткою товару"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Додати в замовлення", callback_data=f"add_{article}")
        ]
    ])
    return keyboard

def get_cart_keyboard(article: str):
    """Кнопки під час введення кількості (Скасувати)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_order")]
    ])
    return keyboard

def get_success_add_keyboard():
    """Кнопка після успішного додавання"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Перейти до кошика", callback_data="view_cart_btn")]
    ])
    return keyboard

def get_cart_actions_keyboard():
    """Кнопки під кошиком (Оформити / Очистити)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сформувати замовлення", callback_data="submit_order")
        ],
        [
            InlineKeyboardButton(text="🗑 Очистити все", callback_data="clear_cart")
        ]
    ])
    return keyboard