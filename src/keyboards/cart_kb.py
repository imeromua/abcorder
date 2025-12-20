from typing import Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_cart_keyboard(article: str) -> InlineKeyboardMarkup:
    """
    Клавіатура, яка показується, коли користувач вводить кількість товару.
    Додаємо кнопку 'Скасувати', щоб вийти з режиму вводу.
    """
    builder = InlineKeyboardBuilder()
    
    # Можна додати пресети (наприклад, +1, +10), але поки тільки Скасування
    builder.button(text="❌ Скасувати", callback_data="cancel_order")
    
    return builder.as_markup()

def get_success_add_keyboard(back_callback: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Показується після успішного додавання товару в кошик.
    Дозволяє перейти в кошик або повернутися до покупок (в каталог).
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🛒 Переглянути кошик", callback_data="view_cart_btn")
    
    if back_callback:
        # Повертає туди, звідки прийшов юзер (в категорію або пошук)
        builder.button(text="🔙 Продовжити покупки", callback_data=back_callback)
    else:
        # Дефолтна кнопка, якщо шляху назад немає
        builder.button(text="🔙 До меню", callback_data="start_menu")
        
    builder.adjust(1)
    return builder.as_markup()

def get_cart_actions_keyboard() -> InlineKeyboardMarkup:
    """
    Дії в самому кошику: Оформити або Очистити.
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(text="✅ Оформити замовлення", callback_data="submit_order")
    builder.button(text="🗑 Очистити кошик", callback_data="clear_cart")
    builder.button(text="🔙 Згорнути", callback_data="cancel_order") # Або delete_message
    
    builder.adjust(1)
    return builder.as_markup()

def get_order_type_keyboard() -> InlineKeyboardMarkup:
    """
    Вибір типу формування файлу замовлення (для менеджерів/адмінів).
    Магазини цього не бачать (у них завжди по відділах).
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🏢 По відділах (ZPT)", callback_data="order_type_dept")
    builder.button(text="🚚 По постачальниках", callback_data="order_type_supp")
    
    builder.button(text="❌ Скасувати", callback_data="cancel_order")
    
    builder.adjust(1)
    return builder.as_markup()

def get_analytics_order_type_keyboard() -> InlineKeyboardMarkup:
    """
    Аналогічний вибір, але для Автозамовлення в аналітиці.
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🏢 Автозамовлення (по відділах)", callback_data="auto_order_dept")
    builder.button(text="🚚 Автозамовлення (по постачальниках)", callback_data="auto_order_supp")
    
    builder.button(text="🔙 Назад", callback_data="analytics_menu") # Якщо є меню аналітики
    
    builder.adjust(1)
    return builder.as_markup()