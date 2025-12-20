import os
from aiogram import Router, F, types
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from loguru import logger

from src.database.db import db
from src.services.exporter import exporter
from src.keyboards.admin_kb import get_export_filter_keyboard

router = Router()

# --- МЕНЮ ЕКСПОРТУ ---

@router.callback_query(F.data == "admin_export")
async def show_export_menu(callback: types.CallbackQuery):
    """Показує меню вибору типу експорту"""
    await callback.message.edit_text(
        "📤 <b>Експорт даних</b>\n\n"
        "Оберіть тип експорту:\n"
        "📦 <b>Вся база (Raw)</b> — єдиний файл з усіма товарами (із кольоровим аналізом).\n"
        "🏢 <b>По відділах</b> — (в розробці) окремі файли для кожного відділу.",
        parse_mode="HTML",
        reply_markup=get_export_filter_keyboard()
    )

# --- ЛОГІКА ЕКСПОРТУ ---

@router.callback_query(F.data == "export_all")
async def run_export_all(callback: types.CallbackQuery):
    """Експорт всієї бази товарів"""
    status_msg = await callback.message.edit_text("⏳ <b>Генерація файлу...</b>\nЦе може зайняти кілька секунд.", parse_mode="HTML")
    
    try:
        logger.info(f"📤 Full Export requested by {callback.from_user.id}")
        
        # 1. Отримуємо всі товари з бази
        # fetch_all повертає список об'єктів Record, які поводяться як словники
        items = await db.fetch_all("SELECT * FROM products ORDER BY department, name")
        
        if not items:
            await status_msg.edit_text("❌ База даних порожня.")
            return

        # 2. Генеруємо файл (з кольоровим стовпчиком DP)
        file_path = await exporter.export_full_base(items)
        
        # 3. Відправляємо файл
        input_file = FSInputFile(file_path)
        await callback.message.answer_document(
            document=input_file,
            caption=f"📦 <b>Повний експорт бази</b>\nТоварів: {len(items)}\n<i>(З урахуванням ABC-аналізу)</i>",
            parse_mode="HTML"
        )
        
        # 4. Прибираємо повідомлення про статус і видаляємо файл з диска
        await status_msg.delete()
        
        # Невеликий хак: даємо телеграму час відправити файл перед видаленням
        # (хоча FSInputFile зазвичай читає одразу, краще підстрахуватись)
        # В реальному проді краще використовувати async worker для очистки, але тут видалимо одразу
        try:
            os.remove(file_path)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Export failed: {e}")
        await status_msg.edit_text(f"❌ Помилка експорту: {e}")

@router.callback_query(F.data == "export_dept")
async def run_export_dept(callback: types.CallbackQuery):
    """Заглушка для експорту по відділах (можна розширити пізніше)"""
    await callback.answer("🚧 Ця функція ще в розробці!", show_alert=True)