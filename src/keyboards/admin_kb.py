from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Головне меню адміністратора"""
    builder = InlineKeyboardBuilder()
    
    # Ряд 1: Користувачі
    builder.button(text="👥 Користувачі", callback_data="admin_users")
    
    # Ряд 2: Імпорти
    builder.button(text="📥 Імпорт (Файл)", callback_data="admin_import_file")
    builder.button(text="🔗 Імпорт (Лінк)", callback_data="admin_import_link")
    
    # Додаємо кнопку локального імпорту
    builder.button(text="📂 Імпорт (Локально)", callback_data="admin_import_local")
    
    # Ряд 3: Експорт
    builder.button(text="📤 Експорт даних", callback_data="admin_export")

    # Схема розташування кнопок: 1 (Users), 3 (Imports), 1 (Export)
    builder.adjust(1, 3, 1)
    return builder.as_markup()

def get_users_list_keyboard(users: list, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    """Список користувачів з пагінацією"""
    builder = InlineKeyboardBuilder()
    
    for user in users:
        u_name = user['full_name'] or f"User {user['user_id']}"
        u_role = user['role']
        text = f"{u_name} [{u_role}]"
        builder.button(text=text, callback_data=f"user_edit_{user['user_id']}")
    
    builder.adjust(1)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"users_page_{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="ignore"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"users_page_{page+1}"))
    
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_main"))
    
    return builder.as_markup()

def get_user_role_keyboard(user_id: int, current_role: str) -> InlineKeyboardMarkup:
    """Вибір нової ролі для користувача"""
    builder = InlineKeyboardBuilder()
    
    roles = [
        ('shop', '🏪 Магазин'), 
        ('patron', '🕴 Патрон'), 
        ('admin', '⚙️ Адмін')
    ]
    
    for role_code, role_name in roles:
        if role_code == current_role:
            text = f"✅ {role_name}" 
        else:
            text = role_name
        builder.button(text=text, callback_data=f"set_role_{user_id}_{role_code}")
    
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Назад до списку", callback_data="admin_users"))
    
    return builder.as_markup()

def get_export_filter_keyboard() -> InlineKeyboardMarkup:
    """Меню вибору типу експорту"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Вся база (Raw)", callback_data="export_all")
    builder.button(text="🏢 По відділах (Split)", callback_data="export_dept")
    
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Скасувати", callback_data="admin_back_main"))
    return builder.as_markup()