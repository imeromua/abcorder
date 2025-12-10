import os
from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from src.config import config
from src.services.importer import importer
from src.database.db import db
from src.states.user_states import AdminStates

admin_router = Router()

# =======================
# 1. ГОЛОВНЕ МЕНЮ АДМІНА
# =======================
@admin_router.message(F.text == "⚙️ Адмінка", F.from_user.id.in_(config.ADMIN_IDS))
async def admin_panel(message: types.Message):
    # Статистика
    users_count = await db.fetch_one("SELECT COUNT(*) FROM users")
    products_count = await db.fetch_one("SELECT COUNT(*) FROM products")
    
    text = (
        f"⚙️ <b>Панель Адміністратора</b>\n\n"
        f"👥 Користувачів: <b>{users_count[0]}</b>\n"
        f"📦 Товарів у базі: <b>{products_count[0]}</b>\n\n"
        "Оберіть дію:"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Імпорт бази", callback_data="admin_import_info")],
        [InlineKeyboardButton(text="📦 Архів замовлень", callback_data="admin_archive_list")],
        [InlineKeyboardButton(text="📢 Розсилка всім", callback_data="admin_broadcast_start")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

# --- ІНФО ПРО ІМПОРТ ---
@admin_router.callback_query(F.data == "admin_import_info")
async def admin_import_info(callback: types.CallbackQuery):
    text = (
        "📥 <b>Як оновити базу товарів?</b>\n\n"
        "1. Просто надішліть мені файл <code>.xlsx</code> або <code>.csv</code> у цей чат.\n"
        "2. Або завантажте файл у папку <code>data/imports</code> і натисніть /load_local\n\n"
        "<i>Структура файлу має відповідати стандарту.</i>"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.message.answer("Повернутись: тисни '⚙️ Адмінка'") 


# =======================
# 2. АРХІВ ЗАМОВЛЕНЬ
# =======================
@admin_router.callback_query(F.data == "admin_archive_list")
async def admin_archive_list(callback: types.CallbackQuery):
    archive_dir = "data/orders_archive"
    if not os.path.exists(archive_dir):
        await callback.answer("Архів порожній", show_alert=True)
        return

    # Отримуємо список файлів, сортуємо за часом (нові зверху)
    files = sorted(
        [os.path.join(archive_dir, f) for f in os.listdir(archive_dir) if f.endswith('.xlsx')],
        key=os.path.getmtime,
        reverse=True
    )
    
    if not files:
        await callback.answer("Архів порожній", show_alert=True)
        return

    # Показуємо останні 5 файлів
    recent_files = files[:5]
    
    kb_builder = []
    for file_path in recent_files:
        filename = os.path.basename(file_path)
        # Callback data має ліміт, тому передаємо тільки назву файлу (якщо вона не дуже довга)
        # Краще обрізати, якщо дуже довга
        short_name = filename if len(filename) < 30 else filename[:27] + "..."
        kb_builder.append([InlineKeyboardButton(text=f"📄 {short_name}", callback_data=f"get_file_{filename}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_builder)
    
    await callback.message.edit_text("📦 <b>Останні 5 файлів з архіву:</b>", parse_mode="HTML", reply_markup=kb)

@admin_router.callback_query(F.data.startswith("get_file_"))
async def admin_get_file(callback: types.CallbackQuery):
    filename = callback.data.replace("get_file_", "")
    file_path = os.path.join("data/orders_archive", filename)
    
    if os.path.exists(file_path):
        await callback.message.answer_document(FSInputFile(file_path))
        await callback.answer()
    else:
        await callback.answer("Файл не знайдено (можливо, видалено)", show_alert=True)


# =======================
# 3. РОЗСИЛКА (Broadcast)
# =======================
@admin_router.callback_query(F.data == "admin_broadcast_start")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📢 <b>Введіть текст повідомлення для розсилки:</b>\n(Або напишіть 'скасувати')")
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_broadcast_text)
async def broadcast_confirm(message: types.Message, state: FSMContext):
    if message.text.lower() == "скасувати":
        await state.clear()
        await message.answer("Скасовано.")
        return

    await state.update_data(text=message.text)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Надіслати всім", callback_data="broadcast_confirm_yes")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="broadcast_cancel")]
    ])
    
    await message.answer(
        f"📢 <b>Перевірте текст:</b>\n\n{message.text}\n\nНадіслати цей текст усім користувачам?", 
        reply_markup=kb, 
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.confirm_broadcast)

@admin_router.callback_query(AdminStates.confirm_broadcast)
async def broadcast_send(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    if callback.data == "broadcast_cancel":
        await state.clear()
        await callback.message.edit_text("❌ Розсилку скасовано.")
        return

    data = await state.get_data()
    text = data['text']
    
    # Отримуємо всіх юзерів
    users = await db.fetch_all("SELECT user_id FROM users")
    count = 0
    
    await callback.message.edit_text("⏳ Розсилаю повідомлення...")
    
    for u in users:
        try:
            await bot.send_message(u['user_id'], text)
            count += 1
        except:
            pass # Юзер заблокував бота
            
    await callback.message.answer(f"✅ <b>Готово!</b> Повідомлення отримали {count} користувачів.")
    await state.clear()


# =======================
# 4. ОБРОБКА ФАЙЛІВ (ІМПОРТ)
# =======================
# (Залишаємо старий код завантаження файлів)
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
        await status_msg.edit_text(f"❌ Помилка: {e}")

@admin_router.message(Command("load_local"), F.from_user.id.in_(config.ADMIN_IDS))
async def cmd_local_import(message: types.Message):
    folder = "data/imports"
    target_file = None
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.startswith("import") and (f.endswith('.xlsx') or f.endswith('.csv')):
                target_file = os.path.join(folder, f)
                break
    
    if not target_file:
        await message.answer("❌ Файл import.xlsx не знайдено.")
        return

    status_msg = await message.answer(f"🕵️‍♂️ Обробляю {target_file}...")
    await process_import(status_msg, target_file)

async def process_import(status_msg: types.Message, file_path: str):
    try:
        await status_msg.edit_text("⚙️ Оновлюю базу...")
        count = await importer.import_file(file_path)
        await status_msg.edit_text(f"✅ <b>Успіх!</b> Опрацьовано товарів: <b>{count}</b>", parse_mode="HTML")
        try: os.remove(file_path)
        except: pass
    except Exception as e:
        await status_msg.edit_text(f"❌ Помилка імпорту: {e}")