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
        "Будь ласка, надішліть файл <code>.xlsx</code> або <code>.csv</code>.\n"
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
        "Надішліть посилання на файл або <b>Google Drive</b>.\n"
        "<i>(Доступ має бути відкритий: Anyone with the link)</i>",
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Скасувати", callback_data="admin_back_main")]
        ])
    )

# 🔥 НОВЕ: ЛОКАЛЬНИЙ ІМПОРТ
@router.callback_query(F.data == "admin_import_local")
async def on_import_local_btn(callback: types.CallbackQuery):
    """Шукає файл у папці на сервері"""
    # Папка, куди зазвичай падають завантаження або куди кладемо вручну
    # Можна використовувати 'data/imports' або 'data/temp'
    search_dir = "data/imports"
    os.makedirs(search_dir, exist_ok=True)
    
    target_file = None
    
    # Шукаємо перший файл, що починається на 'import' і має правильне розширення
    if os.path.exists(search_dir):
        for f in os.listdir(search_dir):
            if f.startswith("import") and f.lower().endswith(('.xlsx', '.csv', '.xlsb')):
                target_file = os.path.join(search_dir, f)
                break
    
    if not target_file:
        await callback.answer("❌ Файл 'data/imports/import*' не знайдено!", show_alert=True)
        return

    status_msg = await callback.message.edit_text(
        f"🕵️‍♂️ <b>Знайдено файл:</b>\n<code>{os.path.basename(target_file)}</code>\n\n⏳ Починаю обробку...", 
        parse_mode="HTML"
    )
    
    # Запускаємо процес (без скачування, бо файл вже локально)
    await process_import(status_msg, target_file)


# --- ХЕНДЛЕРИ ФАЙЛІВ ТА ЛІНКІВ ---

@router.message(AdminStates.waiting_for_import_file, F.document)
async def handle_import_file(message: types.Message, bot: Bot, state: FSMContext):
    doc = message.document
    if not (doc.file_name.endswith('.xlsx') or doc.file_name.endswith('.csv')):
        await message.answer("❌ Формат файлу має бути .xlsx або .csv")
        return

    status_msg = await message.answer("⏳ <b>Починаю завантаження...</b>", parse_mode="HTML")
    file_path = f"data/temp/{doc.file_name}"
    os.makedirs("data/temp", exist_ok=True)
    
    try:
        await bot.download(doc, destination=file_path)
        await process_import(status_msg, file_path)
        await state.clear()
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_msg.edit_text(f"❌ Помилка завантаження: {e}")

@router.message(AdminStates.waiting_for_import_link, F.text)
async def handle_import_link(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if "drive.google.com" in url:
        url = transform_drive_url(url)
        if not url:
            await message.answer("❌ Некоректне посилання Google Drive.")
            return

    status_msg = await message.answer("⏳ <b>Завантажую файл через gdown...</b>", parse_mode="HTML")
    
    try:
        file_path = await download_file(url, "data/temp")
        await process_import(status_msg, file_path)
        await state.clear()
    except Exception as e:
        logger.error(f"Link download error: {e}")
        await status_msg.edit_text(f"❌ Не вдалося завантажити файл: {e}")

# --- ГОЛОВНА ЛОГІКА ІМПОРТУ ---

async def process_import(status_msg: types.Message, file_path: str):
    logger.info(f"⚙️ Processing import file: {file_path}")
    last_update_time = 0
    
    async def progress_updater(current, total, stage="inserting"):
        nonlocal last_update_time
        now = time.time()
        if (now - last_update_time < 3) and current < total and stage != "reading":
            return
        last_update_time = now
        
        if stage == "reading":
            text = "📖 <b>Етап 1/2:</b> Читання файлу (це може зайняти час)..."
        else:
            bar = notifier.make_progress_bar(current, total)
            text = (
                f"💾 <b>Етап 2/2:</b> Запис у базу\n"
                f"{bar}\n"
                f"Опрацьовано: <b>{current} / {total}</b>"
            )
        try:
            if status_msg.html_text != text:
                await status_msg.edit_text(text, parse_mode="HTML")
        except: pass

    try:
        count = await importer.import_file(file_path, status_callback=progress_updater)
        
        await status_msg.edit_text(
            f"✅ <b>Імпорт завершено!</b>\n"
            f"📊 Товарів: <b>{count}</b>\n"
            f"📁 Файл: <code>{os.path.basename(file_path)}</code>",
            parse_mode="HTML"
        )
        
        await notifier.info(status_msg.bot, f"📥 <b>Імпорт OK</b>\nФайл: {os.path.basename(file_path)}\nКількість: {count}")
        
        # Видаляємо файл тільки якщо він був у temp (завантажений). 
        # Якщо він був локальний (data/imports), можна залишити або архівувати.
        if "data/temp" in file_path:
            try: os.remove(file_path)
            except: pass
            
    except Exception as e:
        logger.error(f"❌ Import Logic failed: {e}")
        err_text = str(e)
        if "BadZipFile" in err_text: err_text = "Файл пошкоджено або не Excel."
        await status_msg.edit_text(f"❌ <b>Помилка імпорту</b>\n<code>{err_text}</code>", parse_mode="HTML")