from aiogram import Router, F, types
from aiogram.filters import CommandStart
from src.database.db import db
from src.keyboards.main_menu import get_main_menu
from src.config import config  # <--- Не забудь імпортувати конфіг

common_router = Router()

@common_router.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    
    # 1. Спочатку записуємо/оновлюємо користувача як зазвичай
    await db.execute("""
        INSERT INTO users (user_id, username, full_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id) DO UPDATE 
        SET full_name = $3, username = $2
    """, user.id, user.username, user.full_name)

    # 2. !!! МАГІЯ ТУТ !!! 
    # Якщо ID юзера є в списку адмінів у конфігу -> примусово ставимо роль 'admin'
    if user.id in config.ADMIN_IDS:
        await db.execute("UPDATE users SET role = 'admin' WHERE user_id = $1", user.id)

    # 3. Тепер читаємо роль із бази (вона вже буде правильною)
    row = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", user.id)
    role = row['role']

    # 4. Відповідь
    text = f"Вітаю, {user.full_name}! 👋\n"
    text += f"Ваша роль: <b>{role.upper()}</b>\n\n"
    
    if role == 'shop':
        text += "🛒 Ви можете переглядати каталог і формувати переміщення (по відділах)."
    elif role == 'patron':
        text += "👔 Вам доступна аналітика та вибір типу замовлення (відділи/постачальники)."
    elif role == 'admin':
        text += "⚙️ Вам доступно все + панель керування."

    # 5. Показуємо меню
    await message.answer(
        text, 
        parse_mode="HTML",
        reply_markup=get_main_menu(role)
    )

# Обробка кнопки "Мій профіль"
@common_router.message(F.text == "👤 Мій профіль")
async def profile_handler(message: types.Message):
    await cmd_start(message)