from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_departments_keyboard(departments: list) -> InlineKeyboardMarkup:
    """
    Клавіатура вибору відділу (кореневий рівень).
    departments: список кортежів або словників [(id, name), ...]
    """
    builder = InlineKeyboardBuilder()
    
    for dept in departments:
        # Припускаємо, що dept це словник {'department': 1, 'name': 'Назва'}
        # або кортеж (1, 'Назва')
        d_id = dept.get('department')
        d_name = dept.get('name', f"Відділ {d_id}")
        
        # dept_{id} - сигнал для хендлера відкрити цей відділ
        builder.button(text=d_name, callback_data=f"dept_{d_id}")
    
    builder.adjust(2) # По 2 відділи в ряд
    
    # Кнопка пошуку внизу
    builder.row(InlineKeyboardButton(text="🔍 Пошук товару", callback_data="start_search"))
    
    return builder.as_markup()

def get_categories_keyboard(categories: list, current_path: str, back_callback: str) -> InlineKeyboardMarkup:
    """
    Універсальна клавіатура для підкатегорій.
    categories: список назв підкатегорій ['Напої', 'Снеки']
    current_path: поточний шлях для формування callback (напр. "1:Напої")
    """
    builder = InlineKeyboardBuilder()
    
    for cat_name in categories:
        # Обрізаємо назву, якщо дуже довга (для кнопки)
        btn_text = (cat_name[:30] + '..') if len(cat_name) > 30 else cat_name
        
        # Формуємо callback для наступного рівня
        # cat_navigator розбере цей шлях
        callback = f"nav_{current_path}/{cat_name}"
        
        # *Важливо: telegram має ліміт 64 байти на callback_data. 
        # Якщо шляхи довгі, треба використовувати скорочення або ID (хешування).
        # Тут припускаємо, що вліземо, або потім додамо скорочувач.
        
        builder.button(text=btn_text, callback_data=callback)
        
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback))
    
    return builder.as_markup()

def get_products_keyboard(products: list, page: int, total_pages: int, back_callback: str) -> InlineKeyboardMarkup:
    """
    Список товарів з пагінацією.
    Кнопка товару веде одразу на додавання в кошик (add_...)
    """
    builder = InlineKeyboardBuilder()
    
    for product in products:
        # Текст кнопки: "Cola 0.5 (15.00 грн)"
        # Якщо є залишок, можна додати і його
        price = f"{product['stock_sum']/product['stock_qty']:.2f}" if product['stock_qty'] > 0 else "0.00"
        name = product['name']
        article = product['article']
        
        text = f"{name} | {price} грн"
        
        # add_{article}_{back_callback} 
        # Передаємо back_callback, щоб після додавання повернутися сюди ж
        builder.button(text=text, callback_data=f"add_{article}_{back_callback}")
    
    builder.adjust(1) # Товари в стовпчик
    
    # --- ПАГІНАЦІЯ ---
    nav_row = []
    
    # "nav_products_{path}_{page}"
    # Оскільки back_callback містить шлях (напр "nav_1/Напої"), ми витягуємо його для пагінації
    # Або передаємо чистий шлях окремим аргументом. 
    # Тут спростимо: припустимо, що хендлер знає контекст з state, 
    # а в callback передаємо тільки page.
    
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"page_{page-1}"))
        
    nav_row.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="ignore"))
    
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"page_{page+1}"))
        
    builder.row(*nav_row)
    
    # Кнопка Назад
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback))
    
    return builder.as_markup()