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

# Повернення в меню (для кнопки "Назад")
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
# 2. КЕРУВАННЯ КОРИСТУВАЧАМИ (НОВЕ!)
# =======================

# Список користувачів (Пагінація)
@admin_router.callback_query(F.data.startswith("admin_users_list_"))
async def admin_users_list(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[-1])
    limit = 10
    offset = page * limit
    
    # Витягуємо юзерів
    sql = """
        SELECT user_id, full_name, username, role 
        FROM users 
        ORDER BY joined_at DESC 
        LIMIT $1 OFFSET $2
    """
    users = await db.fetch_all(sql, limit, offset)
    
    # Перетворюємо в список словників
    users_list = [dict(u) for u in users]
    
    await callback.message.edit_text(
        f"👥 <b>Список користувачів (Сторінка {page+1}):</b>\nОберіть користувача для зміни ролі:",
        parse_mode="HTML",
        reply_markup=get_users_list_keyboard(users_list, page)
    )

# Картка редагування користувача
@admin_router.callback_query(F.data.startswith("admin_user_edit_"))
async def admin_user_edit(callback: types.CallbackQuery):
    target_user_id = int(callback.data.split("_")[-1])
    
    user = await db.fetch_one("SELECT * FROM users WHERE user_id = $1", target_user_id)
    
    if not user:
        await callback.answer("Користувача не знайдено", show_alert=True)
        return

    text = (
        f"👤 <b>Редагування користувача</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"📝 Ім'я: {user['full_name']}\n"
        f"🔗 Username: @{user['username']}\n"
        f"📅 Дата реєстрації: {user['joined_at']}\n\n"
        f"🔑 <b>Поточна роль:</b> {user['role'].upper()}"
    )
    
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=get_user_role_keyboard(target_user_id, user['role'])
    )

# Збереження нової ролі
@admin_router.callback_query(F.data.startswith("admin_set_role_"))
async def admin_set_role(callback: types.CallbackQuery, bot: Bot):
    # data: admin_set_role_ID_ROLE
    parts = callback.data.split("_")
    target_user_id = int(parts[3])
    new_role = parts[4]
    
    # Оновлюємо базу
    await db.execute("UPDATE users SET role = $1 WHERE user_id = $2", new_role, target_user_id)
    
    # Повідомляємо адміна
    await callback.answer(f"✅ Роль змінено на {new_role.upper()}")
    
    # Оновлюємо картку (повертаємось до редагування, щоб видно було зміни)
    await admin_user_edit(callback)
    
    # (Опціонально) Можна надіслати повідомлення самому користувачу
    try:
        msg = f"🔔 <b>Ваші права оновлено!</b>\nНова роль: {new_role.upper()}\nНатисніть /start, щоб оновити меню."
        await bot.send_message(target_user_id, msg, parse_mode="HTML")
    except:
        pass

@admin_router.callback_query(F.data == "ignore_click")
async def ignore_click(callback: types.CallbackQuery):
    await callback.answer()


# =======================
# 3. ІНФО ПРО ІМПОРТ
# =======================
@admin_router.callback_query(F.data == "admin_import_info")
async def admin_import_info(callback: types.CallbackQuery):
    text = (
        "📥 <b>Як оновити базу товарів?</b>\n\n"
        "1. Просто надішліть мені файл <code>.xlsx</code> або <code>.csv</code> у цей чат.\n"
        "2. Або завантажте файл у папку <code>data/imports</code> і натисніть /load_local\n\n"
        "<i>Структура файлу має відповідати стандарту.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_main")]])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


# =======================
# 4. АРХІВ ЗАМОВЛЕНЬ
# =======================
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
    for file_path in recent_files:
        filename = os.path.basename(file_path)
        short_name = filename if len(filename) < 30 else filename[:27] + "..."
        kb_builder.append([InlineKeyboardButton(text=f"📄 {short_name}", callback_data=f"get_file_{filename}")])
    
    kb_builder.append([InlineKeyboardButton(text="🗄 Скачати весь архів (ZIP)", callback_data="admin_download_zip")])
    kb_builder.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_main")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_builder)
    
    await callback.message.edit_text("📦 <b>Останні файли з архіву:</b>", parse_mode="HTML", reply_markup=kb)

@admin_router.callback_query(F.data.startswith("get_file_"))
async def admin_get_file(callback: types.CallbackQuery):
    filename = callback.data.replace("get_file_", "")
    file_path = os.path.join("data/orders_archive", filename)
    
    if os.path.exists(file_path):
        await callback.message.answer_document(FSInputFile(file_path))
        await callback.answer()
    else:
        await callback.answer("Файл не знайдено", show_alert=True)

@admin_router.callback_query(F.data == "admin_download_zip")
async def admin_download_zip(callback: types.CallbackQuery):
    archive_dir = "data/orders_archive"
    if not os.path.exists(archive_dir) or not os.listdir(archive_dir):
        await callback.answer("Архів порожній", show_alert=True)
        return

    await callback.message.answer("⏳ <b>Архівую файли...</b>", parse_mode="HTML")
    
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        zip_filename = f"orders_archive_{timestamp}"
        zip_path = f"data/temp/{zip_filename}"
        
        os.makedirs("data/temp", exist_ok=True)
        shutil.make_archive(zip_path, 'zip', archive_dir)
        final_zip_path = zip_path + ".zip"
        
        await callback.message.answer_document(FSInputFile(final_zip_path))
        os.remove(final_zip_path)
        
    except Exception as e:
        await callback.message.answer(f"❌ Помилка архівації: {e}")


# =======================
# 5. РОЗСИЛКА (Broadcast)
# =======================
@admin_router.callback_query(F.data == "admin_broadcast_start")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="broadcast_cancel_input")]
    ])
    
    await callback.message.edit_text(
        "📢 <b>Введіть текст повідомлення для розсилки:</b>\n"
        "(Підтримуються теги &lt;b&gt;, &lt;i&gt; тощо)", 
        parse_mode="HTML",
        reply_markup=kb
    )
    await state.set_state(AdminStates.waiting_for_broadcast_text)

@admin_router.callback_query(F.data == "broadcast_cancel_input")
async def broadcast_cancel_input(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    # Повертаємо в меню
    await show_admin_dashboard(callback.message, is_edit=True)

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
    
    try:
        await message.answer(
            f"📢 <b>Попередній перегляд:</b>\n\n{message.text}\n\nНадіслати це повідомлення всім?", 
            reply_markup=kb, 
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.confirm_broadcast)
    except Exception as e:
        await message.answer(f"❌ <b>Помилка в HTML-тегах!</b>\n{e}")

@admin_router.callback_query(AdminStates.confirm_broadcast)
async def broadcast_send(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    if callback.data == "broadcast_cancel":
        await state.clear()
        await callback.message.edit_text("❌ Розсилку скасовано.")
        return

    data = await state.get_data()
    text = data['text']
    
    users = await db.fetch_all("SELECT user_id FROM users")
    count = 0
    
    await callback.message.edit_text("⏳ Розсилаю повідомлення...")
    
    for u in users:
        try:
            await bot.send_message(u['user_id'], text, parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05)
        except:
            pass 
            
    await callback.message.answer(f"✅ <b>Готово!</b> Повідомлення отримали {count} користувачів.", parse_mode="HTML")
    await state.clear()


# =======================
# 6. ОБРОБКА ФАЙЛІВ (ІМПОРТ)
# =======================
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