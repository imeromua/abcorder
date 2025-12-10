from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- ТОВАРИ ТА КОШИК ---

def get_product_keyboard(article: str, back_callback: str = None):
    # Додаємо шлях назад у кнопку "Додати", щоб після додавання повернутися
    if back_callback:
        add_callback = f"add_{article}_{back_callback}"
    else:
        add_callback = f"add_{article}"

    buttons = [
        [InlineKeyboardButton(text="📥 Додати в замовлення", callback_data=add_callback)]
    ]
    
    if back_callback:
        buttons.append([InlineKeyboardButton(text="⬅️ Назад до списку", callback_data=back_callback)])
    else:
        buttons.append([InlineKeyboardButton(text="❌ Закрити картку", callback_data="close_catalog")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cart_keyboard(article: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_order")]
    ])

def get_success_add_keyboard(back_callback: str = None):
    buttons = [
        [InlineKeyboardButton(text="🛒 Перейти до кошика", callback_data="view_cart_btn")]
    ]
    if back_callback and back_callback != "None":
        buttons.append([InlineKeyboardButton(text="⬅️ Продовжити покупки", callback_data=back_callback)])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cart_actions_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сформувати замовлення", callback_data="submit_order")],
        [InlineKeyboardButton(text="🗑 Очистити все", callback_data="clear_cart")]
    ])

# --- ВИБІР ТИПУ ЗАМОВЛЕННЯ ---

def get_order_type_keyboard():
    """Для звичайного кошика"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏢 По відділах (ЗПТ)", callback_data="order_type_dept"),
            InlineKeyboardButton(text="🏭 По постачальниках", callback_data="order_type_supp")
        ],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="close_catalog")] 
    ])

def get_analytics_order_type_keyboard():
    """Для автозамовлення з аналітики"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏢 По відділах (ЗПТ)", callback_data="auto_order_dept"),
            InlineKeyboardButton(text="🏭 По постачальниках", callback_data="auto_order_supp")
        ],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="close_catalog")] 
    ])

# --- АДМІНКА: КЕРУВАННЯ ЮЗЕРАМИ ---

def get_admin_dashboard_keyboard():
    """Головне меню адміна"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Керування користувачами", callback_data="admin_users_list_0")],
        [InlineKeyboardButton(text="📥 Імпорт бази", callback_data="admin_import_info")],
        [InlineKeyboardButton(text="📦 Архів замовлень", callback_data="admin_archive_list")],
        [InlineKeyboardButton(text="📢 Розсилка всім", callback_data="admin_broadcast_start")]
    ])

def get_users_list_keyboard(users: list, page: int = 0):
    """Список юзерів з пагінацією"""
    builder = InlineKeyboardBuilder()
    
    for u in users:
        # Емодзі ролі
        role_icon = "🛒"
        if u['role'] == 'patron': role_icon = "👔"
        elif u['role'] == 'admin': role_icon = "⚙️"
        
        # Ім'я (обрізаємо якщо довге)
        name = u['full_name'] if u['full_name'] else f"User {u['user_id']}"
        if len(name) > 20: name = name[:18] + ".."
        
        text = f"{role_icon} {name}"
        builder.button(text=text, callback_data=f"admin_user_edit_{u['user_id']}")
    
    builder.adjust(1)
    
    # Кнопки навігації
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_users_list_{page-1}"))
    if len(users) >= 10: # Якщо повна сторінка, припускаємо що є ще
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_users_list_{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
        
    builder.row(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_main"))
    return builder.as_markup()

def get_user_role_keyboard(user_id: int, current_role: str):
    """Вибір ролі для юзера"""
    builder = InlineKeyboardBuilder()
    
    roles = [
        ('shop', '🛒 Магазин'), 
        ('patron', '👔 Патрон (Керівник)'), 
        ('admin', '⚙️ Адмін')
    ]
    
    for role_code, role_name in roles:
        if role_code == current_role:
            text = f"✅ {role_name}"
            callback = "ignore_click"
        else:
            text = role_name
            callback = f"admin_set_role_{user_id}_{role_code}"
        
        builder.button(text=text, callback_data=callback)
        
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ Назад до списку", callback_data="admin_users_list_0"))
    return builder.as_markup()