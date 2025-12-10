import os
from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from src.config import config
from src.services.importer import importer

admin_router = Router()

# --- ВАРІАНТ 1: ЗАВАНТАЖЕННЯ ЧЕРЕЗ ЧАТ (Для малих файлів < 20MB) ---
@admin_router.message(F.document, F.from_user.id.in_(config.ADMIN_IDS))
async def handle_file_upload(message: types.Message, bot: Bot):
    document = message.document
    
    if not (document.file_name.endswith('.xlsx') or document.file_name.endswith('.csv') or document.file_name.endswith('.xlsb')):
        await message.answer("❌ Формат не підтримується.")
        return

    status_msg = await message.answer("⏳ Завантажую файл...")
    file_path = f"data/imports/{document.file_name}"
    
    try:
        await bot.download(document, destination=file_path)
        await process_import(status_msg, file_path)
    except Exception as e:
        await status_msg.edit_text(f"❌ Помилка завантаження: {e}")

# --- ВАРІАНТ 2: ЛОКАЛЬНИЙ ІМПОРТ (Для великих файлів) ---
@admin_router.message(Command("load_local"), F.from_user.id.in_(config.ADMIN_IDS))
async def cmd_local_import(message: types.Message):
    """
    Команда шукає файл 'import.xlsx' або 'import.csv' у папці data/imports
    """
    folder = "data/imports"
    target_file = None
    
    # Шукаємо файл
    for f in os.listdir(folder):
        if f.startswith("import") and (f.endswith(".xlsx") or f.endswith(".csv") or f.endswith(".xlsb")):
            target_file = os.path.join(folder, f)
            break
    
    if not target_file:
        await message.answer(f"❌ Не знайшов файлу `import.xlsx/csv` у папці `{folder}`.\nСкопіюйте його туди вручну.")
        return

    status_msg = await message.answer(f"🕵️‍♂️ Знайшов локальний файл: `{target_file}`. Починаю обробку...")
    await process_import(status_msg, target_file)


# --- СПІЛЬНА ФУНКЦІЯ ОБРОБКИ ---
async def process_import(status_msg: types.Message, file_path: str):
    try:
        await status_msg.edit_text("⚙️ Аналізую дані та оновлюю базу... (Це може зайняти час)")
        
        # Запуск імпортера
        count = await importer.import_file(file_path)
        
        await status_msg.edit_text(
            f"✅ <b>Успіх! Базу оновлено.</b>\n\n"
            f"📥 Опрацьовано товарів: <b>{count}</b>",
            parse_mode="HTML"
        )
        
        # Видаляємо файл після успіху
        os.remove(file_path)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Критична помилка імпорту:\n{str(e)}")