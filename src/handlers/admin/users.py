from aiogram import Router, F, types
from aiogram.exceptions import TelegramBadRequest

from src.database.db import db
from src.keyboards.admin_kb import get_users_list_keyboard, get_user_role_keyboard
from src.services.notifier import notifier

router = Router()

PAGE_SIZE = 10

@router.callback_query(F.data == "admin_users")
async def show_users_list(callback: types.CallbackQuery):
    """Показує першу сторінку користувачів"""
    await render_users_page(callback, page=0)

@router.callback_query(F.data.startswith("users_page_"))
async def paginate_users(callback: types.CallbackQuery):
    """Перемикання сторінок"""
    page = int(callback.data.split("_")[2])
    await render_users_page(callback, page=page)

async def render_users_page(callback: types.CallbackQuery, page: int):
    """Логіка відображення списку з БД"""
    # 1. Рахуємо загальну кількість для пагінації
    count_res = await db.fetch_one("SELECT count(*) as cnt FROM users")
    total_users = count_res['cnt']
    total_pages = (total_users + PAGE_SIZE - 1) // PAGE_SIZE
    
    # 2. Отримуємо зріз користувачів
    offset = page * PAGE_SIZE
    users = await db.fetch_all(
        "SELECT user_id, full_name, username, role FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        PAGE_SIZE, offset
    )
    
    text = (
        f"👥 <b>Користувачі</b> (Всього: {total_users})\n"
        f"Сторінка {page + 1}/{total_pages}\n\n"
        "<i>Натисніть на користувача для редагування ролі.</i>"
    )
    
    try:
        await callback.message.edit_text(
            text, 
            parse_mode="HTML",
            reply_markup=get_users_list_keyboard(users, page, total_pages)
        )
    except TelegramBadRequest:
        await callback.answer() # Щоб не висіло, якщо сторінка не змінилась

# --- РЕДАГУВАННЯ КОРИСТУВАЧА ---

@router.callback_query(F.data.startswith("user_edit_"))
async def edit_user_menu(callback: types.CallbackQuery):
    """Меню редагування конкретного юзера"""
    user_id = int(callback.data.split("_")[2])
    
    user = await db.fetch_one("SELECT * FROM users WHERE user_id = $1", user_id)
    if not user:
        await callback.answer("Користувача не знайдено!", show_alert=True)
        return

    text = (
        f"👤 <b>Редагування користувача</b>\n\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Name: {user['full_name']}\n"
        f"Username: @{user['username']}\n"
        f"Role: <b>{user['role']}</b>\n\n"
        "Оберіть нову роль:"
    )
    
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=get_user_role_keyboard(user_id, user['role'])
    )

@router.callback_query(F.data.startswith("set_role_"))
async def set_user_role(callback: types.CallbackQuery):
    """Збереження нової ролі"""
    parts = callback.data.split("_")
    user_id = int(parts[2])
    new_role = parts[3]
    
    # Оновлюємо в БД
    await db.execute("UPDATE users SET role = $1 WHERE user_id = $2", new_role, user_id)
    
    # Логуємо дію
    admin_name = callback.from_user.full_name
    await notifier.info(
        callback.bot, 
        f"👮‍♂️ <b>Зміна ролі</b>\n"
        f"Адмін: {admin_name}\n"
        f"Користувач ID: {user_id}\n"
        f"Нова роль: <b>{new_role}</b>"
    )
    
    await callback.answer(f"✅ Роль змінено на {new_role}!", show_alert=True)
    
    # Повертаємось до списку користувачів
    await render_users_page(callback, page=0)