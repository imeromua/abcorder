import os
import shutil
import asyncio
from datetime import datetime
from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from src.config import config
from src.services.importer import importer
from src.database.db import db
from src.states.user_states import AdminStates
from src.keyboards.inline import (
    get_admin_dashboard_keyboard, 
    get_users_list_keyboard, 
    get_user_role_keyboard
)

admin_router = Router()

# =======================
# 1. ГОЛОВНЕ МЕНЮ АДМІНА
# =======================
@admin_router.message(F.text == "⚙️ Адмінка", F.from_user.id.in_(config.ADMIN_IDS))
async def admin_panel(message: types.Message):
    await show_admin_dashboard(message)

# Обробка кнопки "Назад в меню"
@admin_router.callback_query(F.data == "admin_back_main")
async def admin_back_main(callback: types.CallbackQuery):
    await show_admin_dashboard(callback.message, is_edit=True)

async def show_admin_dashboard(message: types.Message, is_edit: bool = False):
    users_count = await db.fetch_one("SELECT COUNT(*) FROM users")
    products_count = await db.fetch_one("SELECT COUNT(*) FROM products")
    
    text = (
        f"⚙️ <b>Панель Адміністратора</b>\n\n"
        f"👥 Користувачів: <b>{users_count[0]}</b>\n"
        f"📦 Товарів у базі: <b>{products_count[0]}</b>\n\n"
        "Оберіть дію:"
    )
    
    if is_edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_dashboard_keyboard())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_admin_dashboard_keyboard())


# =======================
# 2. КЕРУВАННЯ КОРИСТУВАЧАМИ
# =======================

# Список користувачів
@admin_router.callback_query(F.data.startswith("admin_users_list_"))
async def admin_users_list(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[-1])
    limit = 10
    offset = page * limit
    
    # Витягуємо список з бази (сортуємо по ID або даті реєстрації)
    # Якщо є поле joined_at - використовуємо його, якщо ні - user_id
    # Припускаємо, що таблиця users проста: user_id, username, full_name, role
    sql = "SELECT user_id, full_name, username, role FROM users ORDER BY user_id LIMIT $1 OFFSET $2"
    users = await db.fetch_all(sql, limit, offset)
    
    users_list = [dict(u) for u in users]
    
    await callback.message.edit_text(
        f"👥 <b>Список користувачів (стор. {page+1}):</b>\nОберіть користувача для зміни прав:",
        parse_mode="HTML",
        reply_markup=get_users_list_keyboard(users_list, page)
    )

# Картка юзера
@admin_router.callback_query(F.data.startswith("admin_user_edit_"))
async def admin_user_edit(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[-1])
    user = await db.fetch_one("SELECT * FROM users WHERE user_id = $1", target_id)
    
    if not user:
        await callback.answer("Користувача не знайдено", show_alert=True)
        return

    username = f"@{user['username']}" if user['username'] else "Немає"
    
    text = (
        f"👤 <b>Редагування користувача</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"📝 Ім'я: {user['full_name']}\n"
        f"🔗 Юзернейм: {username}\n"
        f"🔑 <b>Поточна роль:</b> {user['role'].upper()}"
    )
    
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=get_user_role_keyboard(target_id, user['role'])
    )

# Зміна ролі
@admin_router.callback_query(F.data.startswith("admin_set_role_"))
async def admin_set_role(callback: types.CallbackQuery, bot: Bot):
    # format: admin_set_role_123456_admin
    parts = callback.data.split("_")
    target_id = int(parts[3])
    new_role = parts[4]
    
    await db.execute("UPDATE users SET role = $1 WHERE user_id = $2", new_role, target_id)
    
    await callback.answer(f"✅ Роль змінено на {new_role.upper()}")
    
    # Оновлюємо картку, щоб показати зміни
    await admin_user_edit(callback)
    
    # Сповіщаємо юзера (за бажанням)
    try:
        await bot.send_message(target_id, f"🔔 Ваші права оновлено! Нова роль: <b>{new_role.upper()}</b>.\nНатисніть /start для оновлення меню.", parse_mode="HTML")
    except:
        pass

@admin_router.callback_query(F.data == "ignore_click")
async def ignore_click(callback: types.CallbackQuery):
    await callback.answer()


# =======================
# 3. ІНФО ТА АРХІВ
# =======================
@admin_router.callback_query(F.data == "admin_import_info")
async def admin_import_info(callback: types.CallbackQuery):
    text = (
        "📥 <b>Як оновити базу товарів?</b>\n\n"
        "1. Надішліть файл <code>.xlsx</code> або <code>.csv</code> сюди.\n"
        "2. Або завантажте в <code>data/imports</code> і натисніть /load_local"
    )
    # Кнопка "Назад"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_main")]])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@admin_router.callback_query(F.data == "admin_archive_list")
async def admin_archive_list(callback: types.CallbackQuery):
    archive_dir = "data/orders_archive"
    if not os.path.exists(archive_dir):
        await callback.answer("Архів порожній", show_alert=True)
        return

    files = sorted(
        [os.path.join(archive_dir, f) for f in os.listdir(archive_dir) if f.endswith('.xlsx')],
        key=os.path.getmtime,
        reverse=True
    )
    
    if not files:
        await callback.answer("Архів порожній", show_alert=True)
        return

    recent_files = files[:5]
    kb_builder = []
    for f_path in recent_files:
        fname = os.path.basename(f_path)
        short = fname if len(fname) < 25 else fname[:22] + "..."
        kb_builder.append([InlineKeyboardButton(text=f"📄 {short}", callback_data=f"get_file_{fname}")])
    
    kb_builder.append([InlineKeyboardButton(text="🗄 Скачати весь архів (ZIP)", callback_data="admin_download_zip")])
    kb_builder.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_main")])
    
    await callback.message.edit_text("📦 <b>Архів замовлень (останні 5):</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_builder))

@admin_router.callback_query(F.data.startswith("get_file_"))
async def admin_get_file(callback: types.CallbackQuery):
    fname = callback.data.replace("get_file_", "")
    path = os.path.join("data/orders_archive", fname)
    if os.path.exists(path):
        await callback.message.answer_document(FSInputFile(path))
        await callback.answer()
    else:
        await callback.answer("Файл не знайдено", show_alert=True)

@admin_router.callback_query(F.data == "admin_download_zip")
async def admin_download_zip(callback: types.CallbackQuery):
    archive_dir = "data/orders_archive"
    if not os.path.exists(archive_dir) or not os.listdir(archive_dir):
        await callback.answer("Архів порожній", show_alert=True)
        return

    await callback.message.answer("⏳ Архівую...")
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        zip_name = f"data/temp/archive_{ts}"
        os.makedirs("data/temp", exist_ok=True)
        shutil.make_archive(zip_name, 'zip', archive_dir)
        
        await callback.message.answer_document(FSInputFile(zip_name + ".zip"))
        os.remove(zip_name + ".zip")
    except Exception as e:
        await callback.message.answer(f"❌ Помилка: {e}")


# =======================
# 4. РОЗСИЛКА
# =======================
@admin_router.callback_query(F.data == "admin_broadcast_start")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Скасувати", callback_data="broadcast_cancel_input")]])
    await callback.message.answer("📢 <b>Введіть текст розсилки:</b>", parse_mode="HTML", reply_markup=kb)
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.answer()

@admin_router.callback_query(F.data == "broadcast_cancel_input")
async def broadcast_cancel_input(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_admin_dashboard(callback.message, is_edit=True)

@admin_router.message(AdminStates.waiting_for_broadcast_text)
async def broadcast_confirm(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Надіслати", callback_data="broadcast_confirm_yes")],
        [InlineKeyboardButton(text="❌ Відміна", callback_data="broadcast_cancel")]
    ])
    try:
        await message.answer(f"📢 <b>Прев'ю:</b>\n\n{message.text}", parse_mode="HTML", reply_markup=kb)
        await state.set_state(AdminStates.confirm_broadcast)
    except Exception as e:
        await message.answer(f"❌ Помилка в HTML: {e}")

@admin_router.callback_query(AdminStates.confirm_broadcast)
async def broadcast_send(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    if callback.data == "broadcast_cancel":
        await state.clear()
        await callback.message.edit_text("❌ Скасовано.")
        return

    data = await state.get_data()
    users = await db.fetch_all("SELECT user_id FROM users")
    count = 0
    await callback.message.edit_text("⏳ Розсилаю...")
    
    for u in users:
        try:
            await bot.send_message(u['user_id'], data['text'], parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    
    await callback.message.answer(f"✅ Надіслано {count} користувачам.")
    await state.clear()


# =======================
# 5. ІМПОРТ ФАЙЛІВ
# =======================
@admin_router.message(F.document, F.from_user.id.in_(config.ADMIN_IDS))
async def handle_file_upload(message: types.Message, bot: Bot):
    document = message.document
    if not (document.file_name.endswith('.xlsx') or document.file_name.endswith('.csv') or document.file_name.endswith('.xlsb')):
        await message.answer("❌ Тільки .xlsx, .xlsb, .csv")
        return

    status = await message.answer("⏳ Завантажую...")
    path = f"data/imports/{document.file_name}"
    try:
        await bot.download(document, destination=path)
        await process_import(status, path)
    except Exception as e:
        await status.edit_text(f"❌ Помилка: {e}")

@admin_router.message(Command("load_local"), F.from_user.id.in_(config.ADMIN_IDS))
async def cmd_local_import(message: types.Message):
    folder = "data/imports"
    target = None
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.startswith("import"): target = os.path.join(folder, f); break
    
    if not target:
        await message.answer("❌ Файл не знайдено")
        return
    
    status = await message.answer(f"🕵️‍♂️ Обробляю {target}...")
    await process_import(status, target)

async def process_import(status_msg: types.Message, file_path: str):
    try:
        await status_msg.edit_text("⚙️ Імпортую...")
        count = await importer.import_file(file_path)
        await status_msg.edit_text(f"✅ <b>Готово!</b> Товарів: {count}", parse_mode="HTML")
        try: os.remove(file_path)
        except: pass
    except Exception as e:
        await status_msg.edit_text(f"❌ Помилка: {e}")