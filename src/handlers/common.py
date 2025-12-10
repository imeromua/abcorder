from aiogram import Router, F, types
from aiogram.filters import CommandStart
from src.database.db import db
from src.keyboards.main_menu import get_main_menu

common_router = Router()

@common_router.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    
    # 1. Записуємо користувача в БД (якщо його там немає)
    await db.execute("""
        INSERT INTO users (user_id, username, full_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id) DO UPDATE 
        SET full_name = $3, username = $2
    """, user.id, user.username, user.full_name)

    # 2. Перевіряємо, яка у нього роль зараз
    row = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", user.id)
    role = row['role']

    # 3. Відповідь
    text = f"Вітаю, {user.full_name}! 👋\n"
    text += f"Ваша роль: <b>{role.upper()}</b>\n\n"
    
    if role == 'shop':
        text += "Ви можете переглядати каталог і формувати переміщення."
    elif role == 'patron':
        text += "Вам доступна аналітика і закупівля на РЦ."
    elif role == 'admin':
        text += "Доступно керування базою даних."

    # 4. Показуємо меню (передаємо ID, щоб перевірити, чи показувати кнопку адміна)
    await message.answer(
        text, 
        parse_mode="HTML",
        reply_markup=get_main_menu(user.id)
    )

# Обробка кнопки "Мій профіль" (просто дублює старт)
@common_router.message(F.text == "👤 Мій профіль")
async def profile_handler(message: types.Message):
    await cmd_start(message)