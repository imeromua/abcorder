from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from src.config import config
from src.database.db import db
from src.keyboards.admin_kb import get_admin_dashboard_keyboard

router = Router()

# Вхід через команду /admin або кнопку
@router.message(Command("admin"))
@router.message(F.text == "⚙️ Адмінка")
async def admin_panel(message: types.Message, state: FSMContext):
    # Перевірка прав (безпека)
    if message.from_user.id not in config.ADMIN_IDS:
        # Можна перевірити ще й роль в БД, якщо треба
        return 

    await state.clear()
    await show_admin_dashboard(message)

# Кнопка "Назад" в адмінці
@router.callback_query(F.data == "admin_back_main")
async def admin_back_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_admin_dashboard(callback.message, is_edit=True)

async def show_admin_dashboard(message: types.Message, is_edit: bool = False):
    """Показує головну статистику та меню"""
    # Отримуємо свіжу статистику
    users_count = await db.fetch_one("SELECT COUNT(*) as cnt FROM users")
    products_count = await db.fetch_one("SELECT COUNT(*) as cnt FROM products")
    
    text = (
        f"⚙️ <b>Панель Адміністратора</b>\n\n"
        f"👥 Користувачів: <b>{users_count['cnt']}</b>\n"
        f"📦 Товарів у базі: <b>{products_count['cnt']}</b>\n\n"
        "Оберіть дію або <b>надішліть файл</b> (.xlsx) для швидкого імпорту."
    )
    
    if is_edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_dashboard_keyboard())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_admin_dashboard_keyboard())