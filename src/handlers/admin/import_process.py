import os
import time
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from src.config import config
from src.services.importer import importer
from src.services.notifier import notifier
from src.utils.text_parsers import transform_drive_url
from src.utils.files import download_file

# Визначаємо стани для адмінки
class AdminStates(StatesGroup):
    waiting_for_import_file = State()
    waiting_for_import_link = State()

router = Router()

# --- КНОПКИ МЕНЮ ---

@router.callback_query(F.data == "admin_import_file")
async def on_import_file_btn(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_import_file)
    await callback.message.edit_text(
        "📥 <b>Завантаження файлу</b>\n\n"
        "Будь ласка, надішліть файл <code>.xlsx</code> або <code>.csv</code> з базою товарів.\n"
        "<i>Максимальний розмір: 20 МБ.</i>",
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Скасувати", callback_data="admin_back_main")]
        ])
    )

@router.callback_query(F.data == "admin_import_link")
async def on_import_link_btn(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_import_link)
    await callback.message.edit_text(
        "🔗 <b>Завантаження за посиланням</b>\n\n"
        "Надішліть пряме посилання на файл або посилання на <b>Google Drive</b>.\n"
        "<i>(Переконайтесь, що доступ відкритий для всіх, хто має посилання)</i>",
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Скасувати", callback_data="admin_back_main")]
        ])
    )

# --- ХЕНДЛЕРИ ФАЙЛІВ ТА ЛІНКІВ ---

@router.message(AdminStates.waiting_for_import_file, F.document)
async def handle_import_file(message: types.Message, bot: Bot, state: FSMContext):
    doc = message.document
    
    # Перевірка розширення
    if not (doc.file_name.endswith('.xlsx') or doc.file_name.endswith('.csv')):
        await message.answer("❌ Формат файлу має бути .xlsx або .csv")
        return

    status_msg = await message.answer("⏳ <b>Починаю завантаження файлу...</b>", parse_mode="HTML")
    
    # Шлях для збереження
    file_path = f"data/temp/{doc.file_name}"
    os.makedirs("data/temp", exist_ok=True)
    
    try:
        # Завантажуємо файл з Telegram
        await bot.download(doc, destination=file_path)
        
        # Запускаємо процес
        await process_import(status_msg, file_path)
        await state.clear()
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_msg.edit_text(f"❌ Помилка завантаження: {e}")

@router.message(AdminStates.waiting_for_import_link, F.text)
async def handle_import_link(message: types.Message, state: FSMContext):
    url = message.text.strip()
    
    # Обробка Google Drive посилань
    if "drive.google.com" in url:
        url = transform_drive_url(url)
        if not url:
            await message.answer("❌ Некоректне посилання Google Drive.")
            return

    status_msg = await message.answer("⏳ <b>Завантажую файл з інтернету...</b>", parse_mode="HTML")
    
    try:
        # Завантажуємо файл за лінком (використовуємо утиліту)
        file_path = await download_file(url, "data/temp")
        
        # Запускаємо процес
        await process_import(status_msg, file_path)
        await state.clear()
        
    except Exception as e:
        logger.error(f"Link download error: {e}")
        await status_msg.edit_text(f"❌ Не вдалося завантажити файл: {e}")

# --- ГОЛОВНА ЛОГІКА ІМПОРТУ (З Прогрес-баром) ---

async def process_import(status_msg: types.Message, file_path: str):
    logger.info(f"⚙️ Processing import file: {file_path}")
    
    # Змінна для Anti-Flood (щоб не спамити редагуванням)
    last_update_time = 0
    
    async def progress_updater(current, total, stage="inserting"):
        nonlocal last_update_time
        
        # Оновлюємо не частіше ніж раз на 3 секунди
        now = time.time()
        if (now - last_update_time < 3) and current < total and stage != "reading":
            return

        last_update_time = now
        
        if stage == "reading":
            text = "📖 <b>Етап 1/2:</b> Читання та аналіз файлу...\n<i>(Це може зайняти хвилину для великих файлів)</i>"
        else:
            bar = notifier.make_progress_bar(current, total)
            text = (
                f"💾 <b>Етап 2/2:</b> Запис у базу\n"
                f"{bar}\n"
                f"Опрацьовано: <b>{current} / {total}</b>"
            )
        
        try:
            # Перевірка на зміну тексту, щоб уникнути помилок API
            if status_msg.html_text != text:
                await status_msg.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    try:
        # Виклик сервісу імпорту
        count = await importer.import_file(file_path, status_callback=progress_updater)
        
        # Успіх
        await status_msg.edit_text(
            f"✅ <b>Імпорт завершено успішно!</b>\n\n"
            f"📊 Додано/Оновлено товарів: <b>{count}</b>\n"
            f"📁 Файл: <code>{os.path.basename(file_path)}</code>",
            parse_mode="HTML"
        )
        
        # Лог адмінам
        await notifier.info(
            status_msg.bot, 
            f"📥 <b>Імпорт Successful</b>\n"
            f"Файл: {os.path.basename(file_path)}\n"
            f"Кількість: {count}"
        )
        
        # Видаляємо тимчасовий файл
        try:
            os.remove(file_path)
        except:
            pass
            
    except Exception as e:
        logger.error(f"❌ Import Logic failed: {e}")
        
        err_text = str(e)
        if "BadZipFile" in err_text:
            err_text = "Файл пошкоджено або це не коректний Excel."
            
        await status_msg.edit_text(
            f"❌ <b>Критична помилка імпорту</b>\n\n"
            f"Деталі:\n<code>{err_text}</code>",
            parse_mode="HTML"
        )