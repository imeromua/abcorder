from typing import Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_cart_keyboard(article: str) -> InlineKeyboardMarkup:
    """
    Клавіатура додавання в кошик.
    [ЗМІНА] Додані кнопки +1, +5, +10.
    """
    builder = InlineKeyboardBuilder()
    
    # Новий ряд кнопок
    builder.row(
        InlineKeyboardButton(text="+1", callback_data="qty_1"),
        InlineKeyboardButton(text="+5", callback_data="qty_5"),
        InlineKeyboardButton(text="+10", callback_data="qty_10"),
    )
    
    builder.row(InlineKeyboardButton(text="🔙 Скасувати", callback_data="cancel_order"))
    
    return builder.as_markup()

def get_success_add_keyboard(back_callback: Optional[str] = None) -> InlineKeyboardMarkup:
    """Кнопки після успішного додавання"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🛒 Переглянути кошик", callback_data="view_cart_btn")
    
    if back_callback:
        builder.button(text="🔙 Продовжити покупки", callback_data=back_callback)
    else:
        builder.button(text="📂 До каталогу", callback_data="start_menu")
        
    builder.adjust(1)
    return builder.as_markup()

def get_cart_actions_keyboard() -> InlineKeyboardMarkup:
    """Дії в кошику"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Відправити замовлення", callback_data="submit_order"))
    builder.row(InlineKeyboardButton(text="🗑 Очистити кошик", callback_data="clear_cart"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="start_menu"))
    return builder.as_markup()

def get_order_type_keyboard() -> InlineKeyboardMarkup:
    """Вибір типу групування"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏢 По відділах", callback_data="order_type_dept"))
    builder.row(InlineKeyboardButton(text="🏭 По постачальниках", callback_data="order_type_supp"))
    return builder.as_markup()

def get_analytics_order_type_keyboard() -> InlineKeyboardMarkup:
    """Аналогічно для аналітики"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏢 Автозамовлення (по відділах)", callback_data="auto_order_dept"))
    builder.row(InlineKeyboardButton(text="🚚 Автозамовлення (по постачальниках)", callback_data="auto_order_supp"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="analytics_menu"))
    return builder.as_markup()