from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# =======================
# 1. ТОВАРИ ТА КОШИК
# =======================

def get_product_keyboard(article: str, back_callback: str = None):
    """Кнопки під карткою товару: Додати та Назад/Закрити"""
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
    """Кнопка скасування під час введення кількості"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_order")]
    ])

def get_success_add_keyboard(back_callback: str = None):
    """Кнопки після успішного додавання товару"""
    buttons = [
        [InlineKeyboardButton(text="🛒 Перейти до кошика", callback_data="view_cart_btn")]
    ]
    
    if back_callback and back_callback != "None":
        buttons.append([InlineKeyboardButton(text="⬅️ Продовжити покупки", callback_data=back_callback)])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cart_actions_keyboard():
    """Кнопки в кошику: Сформувати або Очистити"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сформувати замовлення", callback_data="submit_order")
        ],
        [
            InlineKeyboardButton(text="🗑 Очистити все", callback_data="clear_cart")
        ]
    ])

def get_order_type_keyboard():
    """Вибір типу групування замовлення"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏢 По відділах (ЗПТ)", callback_data="order_type_dept"),
            InlineKeyboardButton(text="🏭 По постачальниках", callback_data="order_type_supp")
        ],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="close_catalog")] 
    ])

def get_analytics_order_type_keyboard():
    """Вибір типу замовлення з аналітики"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏢 По відділах (ЗПТ)", callback_data="auto_order_dept"),
            InlineKeyboardButton(text="🏭 По постачальниках", callback_data="auto_order_supp")
        ],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="close_catalog")] 
    ])


# =======================
# 2. АДМІН-ПАНЕЛЬ
# =======================

def get_admin_dashboard_keyboard():
    """Головне меню адміна"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Керування користувачами", callback_data="admin_users_list_0")],
        [InlineKeyboardButton(text="📦 Архів замовлень", callback_data="admin_archive_list")],
        [
            InlineKeyboardButton(text="📥 Меню Імпорту", callback_data="admin_import_menu"),
            InlineKeyboardButton(text="📤 Експорт бази", callback_data="admin_export_menu")
        ],
        [InlineKeyboardButton(text="📢 Розсилка всім", callback_data="admin_broadcast_start")]
    ])


# --- Керування юзерами ---

def get_users_list_keyboard(users: list, page: int = 0):
    """Список юзерів з пагінацією"""
    builder = InlineKeyboardBuilder()
    
    for u in users:
        # Емодзі ролі
        role_icon = "🛒"
        if u['role'] == 'patron': role_icon = "👔"
        elif u['role'] == 'admin': role_icon = "⚙️"
        
        # Ім'я
        name = u['full_name'] if u['full_name'] else f"User {u['user_id']}"
        if len(name) > 20: name = name[:18] + ".."
        
        text = f"{role_icon} {name}"
        builder.button(text=text, callback_data=f"admin_user_edit_{u['user_id']}")
    
    builder.adjust(1)
    
    # Кнопки навігації
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_users_list_{page-1}"))
    if len(users) >= 10: # Припускаємо, що є ще сторінка
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
        ('patron', '👔 Патрон'), 
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


# --- Імпорт ---

def get_import_menu_keyboard():
    """Меню вибору методу імпорту"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Прямий файл (.xlsx/.csv/.zip)", callback_data="import_start_direct")],
        [InlineKeyboardButton(text="🔗 За лінком (Google Drive)", callback_data="import_start_link")],
        [InlineKeyboardButton(text="📂 Локальний (data/imports)", callback_data="import_start_local")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_main")]
    ])

def get_cancel_import_keyboard():
    """Кнопка скасування процесу імпорту"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати імпорт", callback_data="import_cancel")]
    ])


# --- Експорт ---

def get_export_menu_keyboard():
    """Меню експорту"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Вивантажити ВСЕ", callback_data="export_run_full")],
        [InlineKeyboardButton(text="🏢 Вибрати відділ", callback_data="export_select_dept")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="admin_back_main")]
    ])

def get_dept_export_keyboard(depts: list):
    """Кнопки вибору відділу для експорту"""
    builder = InlineKeyboardBuilder()
    for d in depts:
        builder.button(text=f"Відділ {d}", callback_data=f"export_dept_{d}")
    
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_export_menu"))
    return builder.as_markup()