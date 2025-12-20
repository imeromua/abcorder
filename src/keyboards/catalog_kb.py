from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_departments_keyboard(departments: list) -> InlineKeyboardMarkup:
    """Клавіатура вибору відділу"""
    builder = InlineKeyboardBuilder()
    
    for dept in departments:
        d_id = dept.get('department')
        d_name = dept.get('name', f"Відділ {d_id}")
        builder.button(text=d_name, callback_data=f"dept_{d_id}")
    
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🔍 Пошук товару", callback_data="start_search"))
    return builder.as_markup()

def get_categories_keyboard(categories_data: list, back_callback: str) -> InlineKeyboardMarkup:
    """
    categories_data: список словників [{'name': 'Назва', 'callback': 'nav_xyz123'}, ...]
    """
    builder = InlineKeyboardBuilder()
    
    for item in categories_data:
        name = item['name']
        # Обрізаємо назву візуально, якщо довга
        btn_text = (name[:30] + '..') if len(name) > 30 else name
        
        # Callback data вже скорочена в хендлері
        builder.button(text=btn_text, callback_data=item['callback'])
        
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback))
    return builder.as_markup()

def get_products_keyboard(products: list, page: int, total_pages: int, back_callback: str) -> InlineKeyboardMarkup:
    """Список товарів"""
    builder = InlineKeyboardBuilder()
    
    for product in products:
        price = f"{product['stock_sum']/product['stock_qty']:.2f}" if product['stock_qty'] > 0 else "0.00"
        name = product['name']
        article = product['article']
        
        text = f"{name} | {price} грн"
        
        # У товарах callback теж може бути довгим через back_callback
        # Але add_{article} зазвичай короткий.
        # back_callback тут вже скорочений (приходить з хендлера)
        builder.button(text=text, callback_data=f"add_{article}_{back_callback}")
    
    builder.adjust(1)
    
    # Пагінація
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"page_{page-1}"))
    
    nav_row.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="ignore"))
    
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"page_{page+1}"))
        
    builder.row(*nav_row)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback))
    
    return builder.as_markup()