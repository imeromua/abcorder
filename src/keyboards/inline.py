from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_product_keyboard(article: str):
    """Кнопки під карткою товару"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            # У callback_data зашиваємо артикул: "add_10309911"
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