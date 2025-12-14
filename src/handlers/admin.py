import os
import shutil
import asyncio
import aiohttp
import re
import zipfile
from datetime import datetime
from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from src.config import config
from src.services.importer import importer
from src.services.exporter import exporter
from src.services.notifier import notifier
from src.phrases import get_random
from src.database.db import db
from src.states.user_states import AdminStates
from src.keyboards.inline import (
    get_admin_dashboard_keyboard, 
    get_users_list_keyboard, 
    get_user_role_keyboard,
    get_import_menu_keyboard,
    get_cancel_import_keyboard,
    get_export_menu_keyboard,
    get_dept_export_keyboard
)

admin_router = Router()

def transform_drive_url(url: str) -> str:
    """Перетворює посилання на перегляд Google Drive у посилання на скачування"""
    file_id_match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url) or re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if file_id_match and "drive.google.com" in url:
        return f"https://drive.google.com/uc?export=download&id={file_id_match.group(1)}"
    return url

# =======================
# 1. ГОЛОВНЕ МЕНЮ АДМІНА
# =======================
@admin_router.message(F.text == "⚙️ Адмінка", F.from_user.id.in_(config.ADMIN_IDS))
async def admin_panel(message: types.Message):
    await show_admin_dashboard(message)

@admin_router.callback_query(F.data == "admin_back_main")
async def admin_back_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_admin_dashboard(callback.message, is_edit=True)

async def show_admin_dashboard(message: types.Message, is_edit: bool = False):
    users_count = await db.fetch_one("SELECT COUNT(*) FROM users")
    products_count = await db.fetch_one("SELECT COUNT(*) FROM products")
    
    text = (
        f"⚙️ <b>Панель Адміністратора</b>\n\n"
        f"👥 Користувачів: <b>{users_count[0]}</b>\n"
        f"📦 Товарів у базі: <b>{products_count[0]}</b>\n\n"
        "Оберіть дію або <b>надішліть файл</b> для імпорту."
    )
    
    if is_edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_dashboard_keyboard())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_admin_dashboard_keyboard())


# =======================
# 2. КЕРУВАННЯ КОРИСТУВАЧАМИ
# =======================
@admin_router.callback_query(F.data.startswith("admin_users_list_"))
async def admin_users_list(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[-1])
    limit = 10
    offset = page * limit
    
    sql = "SELECT user_id, full_name, username, role FROM users ORDER BY user_id LIMIT $1 OFFSET $2"
    users = await db.fetch_all(sql, limit, offset)
    
    users_list = [dict(u) for u in users]
    
    await callback.message.edit_text(
        f"👥 <b>Список користувачів (стор. {page+1}):</b>\nОберіть користувача для зміни прав:",
        parse_mode="HTML",
        reply_markup=get_users_list_keyboard(users_list, page)
    )

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

@admin_router.callback_query(F.data.startswith("admin_set_role_"))
async def admin_set_role(callback: types.CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    target_id = int(parts[3])
    new_role = parts[4]
    
    await db.execute("UPDATE users SET role = $1 WHERE user_id = $2", new_role, target_id)
    
    await callback.answer(f"✅ Роль змінено на {new_role.upper()}")
    
    # Оновлюємо картку
    await admin_user_edit(callback)
    
    # Сповіщаємо юзера
    try:
        await bot.send_message(target_id, f"🔔 Ваші права оновлено! Нова роль: <b>{new_role.upper()}</b>.\nНатисніть /start.", parse_mode="HTML")
    except:
        pass

@admin_router.callback_query(F.data == "ignore_click")
async def ignore_click(callback: types.CallbackQuery):
    await callback.answer()


# =======================
# 3. МЕНЮ ІМПОРТУ
# =======================
@admin_router.callback_query(F.data == "admin_import_menu")
async def admin_import_menu(callback: types.CallbackQuery):
    text = (
        "📥 <b>Меню Імпорту</b>\n\n"
        "Оберіть спосіб оновлення бази товарів:\n"
        "1️⃣ <b>Прямий файл:</b> Підтримуються .xlsx, .csv та <b>.zip</b> (архіви).\n"
        "2️⃣ <b>За лінком:</b> Google Drive / Прямі посилання.\n"
        "3️⃣ <b>Локальний:</b> Якщо файл вже на сервері (data/imports)."
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_import_menu_keyboard())

# --- 3.1 Прямий імпорт (Файл) ---
@admin_router.callback_query(F.data == "import_start_direct")
async def import_start_direct(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📤 <b>Надішліть файл (.xlsx, .csv, .zip)</b>:", 
        parse_mode="HTML", 
        reply_markup=get_cancel_import_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_import_file)

@admin_router.message(AdminStates.waiting_for_import_file, F.document)
async def handle_import_file(message: types.Message, bot: Bot, state: FSMContext):
    doc = message.document
    allowed_ext = ('.xlsx', '.csv', '.xlsb', '.zip')
    
    if not doc.file_name.lower().endswith(allowed_ext):
        await message.answer("❌ Формат не підтримується. Тільки Excel, CSV або ZIP.")
        return

    status = await message.answer("⏳ Завантажую файл...")
    path = f"data/imports/{doc.file_name}"
    os.makedirs("data/imports", exist_ok=True)
    
    try:
        await bot.download(doc, destination=path)
        await process_import_wrapper(status, path)
        await state.clear()
    except Exception as e:
        await status.edit_text(f"❌ Помилка завантаження: {e}")

# --- 3.2 Імпорт за посиланням ---
@admin_router.callback_query(F.data == "import_start_link")
async def import_start_link(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔗 <b>Надішліть посилання (файл або Google Drive):</b>", 
        parse_mode="HTML", 
        reply_markup=get_cancel_import_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_import_link)

@admin_router.message(AdminStates.waiting_for_import_link, F.text)
async def handle_import_link(message: types.Message, state: FSMContext):
    url = transform_drive_url(message.text.strip())
    status = await message.answer("⏳ З'єднуюсь з сервером...")
    
    os.makedirs("data/imports", exist_ok=True)
    
    # Тимчасове ім'я, розширення визначимо пізніше або спробуємо вгадати
    path = "data/imports/downloaded_import.xlsx" 
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await status.edit_text(f"❌ Помилка доступу (код {response.status})")
                    return
                
                # Якщо це ZIP, змінюємо розширення
                if "zip" in response.headers.get("Content-Type", ""):
                    path = "data/imports/downloaded_import.zip"

                with open(path, 'wb') as f:
                    while True:
                        chunk = await response.content.read(1024*1024)
                        if not chunk: break
                        f.write(chunk)
        
        await status.edit_text("✅ Завантажено. Починаю обробку...")
        await process_import_wrapper(status, path)
        await state.clear()
    except Exception as e:
        await status.edit_text(f"❌ Помилка скачування: {e}")

# --- 3.3 Локальний імпорт ---
@admin_router.callback_query(F.data == "import_start_local")
async def import_start_local(callback: types.CallbackQuery):
    folder = "data/imports"
    target = None
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.startswith("import") and f.lower().endswith(('.xlsx', '.csv', '.zip')):
                target = os.path.join(folder, f)
                break
    
    if not target:
        await callback.answer("❌ Файл 'import*' не знайдено", show_alert=True)
        return
    
    msg = await callback.message.answer(f"🕵️‍♂️ Обробляю {os.path.basename(target)}...")
    await process_import_wrapper(msg, target)

# --- Скасування імпорту ---
@admin_router.callback_query(F.data == "import_cancel")
async def import_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Імпорт скасовано.")
    await asyncio.sleep(1)
    await show_admin_dashboard(callback.message, is_edit=True)


# =======================
# 4. ОБРОБКА ФАЙЛІВ (WRAPPER)
# =======================
async def process_import_wrapper(status_msg: types.Message, file_path: str):
    """Обгортка для розпакування ZIP перед імпортом"""
    target_file = file_path
    temp_dir = None
    
    # Якщо це ZIP архів
    if file_path.lower().endswith('.zip'):
        await status_msg.edit_text("🗜 Розпаковую архів...")
        
        temp_dir = os.path.join("data/imports", f"unzip_{datetime.now().strftime('%H%M%S')}")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Шукаємо валідний файл всередині
            found_file = None
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    if f.lower().endswith(('.xlsx', '.csv', '.xlsb')) and not f.startswith('~$'):
                        found_file = os.path.join(root, f)
                        break
                if found_file: break
            
            if found_file:
                target_file = found_file
            else:
                await status_msg.edit_text("❌ В архіві не знайдено файлів Excel/CSV.")
                shutil.rmtree(temp_dir)
                try: os.remove(file_path)
                except: pass
                return
                
        except zipfile.BadZipFile:
            await status_msg.edit_text("❌ Помилка: Некоректний ZIP архів.")
            try: os.remove(file_path)
            except: pass
            if temp_dir: shutil.rmtree(temp_dir)
            return

    # Запускаємо основний імпорт
    await process_import(status_msg, target_file)
    
    # Прибираємо сміття
    if temp_dir:
        try: shutil.rmtree(temp_dir)
        except: pass
    
    # Видаляємо вихідний завантажений файл
    if os.path.exists(file_path):
        try: os.remove(file_path)
        except: pass

async def process_import(status_msg: types.Message, file_path: str):
    try:
        await status_msg.edit_text("⚙️ Імпортую дані в базу...")
        count = await importer.import_file(file_path)
        
        # Веселе повідомлення + Лог
        success_text = get_random("import_success")
        await status_msg.edit_text(f"{success_text}\n\n📊 Опрацьовано: <b>{count}</b> товарів.", parse_mode="HTML")
        await notifier.info(status_msg.bot, f"📥 <b>Імпорт успішний!</b>\nФайл: {os.path.basename(file_path)}\nКількість: {count}")
        
    except Exception as e:
        # Лог помилки + Веселе повідомлення юзеру
        await notifier.error(status_msg.bot, f"❌ Помилка імпорту файлу {os.path.basename(file_path)}", e)
        
        error_header = get_random("error_critical")
        await status_msg.edit_text(f"{error_header}\n\nТехнічні деталі:\n<code>{e}</code>", parse_mode="HTML")


# =======================
# 5. ЕКСПОРТ БАЗИ
# =======================
@admin_router.callback_query(F.data == "admin_export_menu")
async def admin_export_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📤 <b>Експорт бази товарів</b>\n\nОберіть режим:",
        parse_mode="HTML",
        reply_markup=get_export_menu_keyboard()
    )

@admin_router.callback_query(F.data == "export_run_full")
async def export_run_full(callback: types.CallbackQuery):
    await perform_export(callback, dept_filter=None)

@admin_router.callback_query(F.data == "export_select_dept")
async def export_select_dept(callback: types.CallbackQuery):
    rows = await db.fetch_all("SELECT DISTINCT department FROM products ORDER BY department")
    depts = [r['department'] for r in rows if r['department'] is not None]
    
    if not depts:
        await callback.answer("Відділи не знайдені", show_alert=True)
        return

    await callback.message.edit_text(
        "🏢 <b>Оберіть відділ для експорту:</b>",
        parse_mode="HTML",
        reply_markup=get_dept_export_keyboard(depts)
    )

@admin_router.callback_query(F.data.startswith("export_dept_"))
async def export_run_dept(callback: types.CallbackQuery):
    dept_id = int(callback.data.split("_")[-1])
    await perform_export(callback, dept_filter=dept_id)

async def perform_export(callback: types.CallbackQuery, dept_filter=None):
    mode_text = f"Відділ {dept_filter}" if dept_filter else "ВСЯ БАЗА"
    await callback.message.edit_text(f"⏳ <b>Вивантажую ({mode_text})...</b>", parse_mode="HTML")
    
    try:
        # Отримуємо дані
        if dept_filter:
            sql = """
                SELECT department, article, name, category_path, supplier, 
                       resident, cluster, sales_qty, sales_sum, stock_qty, stock_sum
                FROM products WHERE department = $1
            """
            rows = await db.fetch_all(sql, dept_filter)
        else:
            sql = """
                SELECT department, article, name, category_path, supplier, 
                       resident, cluster, sales_qty, sales_sum, stock_qty, stock_sum
                FROM products
            """
            rows = await db.fetch_all(sql)
        
        if not rows:
            await callback.message.answer("❌ Даних не знайдено.")
            return

        items = [dict(r) for r in rows]
        
        # Генеруємо Excel
        file_path = await exporter.export_full_base(items, department_filter=dept_filter)
        
        # --- РОЗУМНА АРХІВАЦІЯ ---
        file_size = os.path.getsize(file_path)
        limit_bytes = 19 * 1024 * 1024 # 19 MB
        
        final_file_path = file_path
        was_zipped = False
        
        if file_size > limit_bytes:
            await callback.message.edit_text(f"📦 Файл великий ({file_size // 1024 // 1024} MB), пакую в ZIP...", parse_mode="HTML")
            
            zip_path = file_path + ".zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(file_path, os.path.basename(file_path))
            
            os.remove(file_path)
            final_file_path = zip_path
            was_zipped = True
        
        caption = f"✅ <b>Експорт: {mode_text}</b>\nРядків: {len(items)}"
        if was_zipped:
            caption += "\n🗜 <i>Файл стиснуто в архів</i>"

        await callback.message.answer_document(FSInputFile(final_file_path), caption=caption, parse_mode="HTML")
        
        try: os.remove(final_file_path)
        except: pass
        
        await callback.message.answer("Готово", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Меню", callback_data="admin_back_main")]]))
        
    except Exception as e:
        await notifier.error(callback.bot, "Export Error", e)
        error_header = get_random("error_critical")
        await callback.message.answer(f"{error_header}\n\n{e}", parse_mode="HTML")


# =======================
# 6. АРХІВ ЗАМОВЛЕНЬ
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

    msg = await callback.message.answer("⏳ Архівую...")
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        zip_name = f"data/temp/archive_{ts}"
        os.makedirs("data/temp", exist_ok=True)
        shutil.make_archive(zip_name, 'zip', archive_dir)
        
        await callback.message.answer_document(FSInputFile(zip_name + ".zip"))
        await msg.delete()
        os.remove(zip_name + ".zip")
    except Exception as e:
        await msg.edit_text(f"❌ Помилка: {e}")


# =======================
# 7. РОЗСИЛКА
# =======================
@admin_router.callback_query(F.data == "admin_broadcast_start")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Скасувати", callback_data="broadcast_cancel_input")]])
    await callback.message.edit_text("📢 <b>Введіть текст розсилки:</b>", parse_mode="HTML", reply_markup=kb)
    await state.set_state(AdminStates.waiting_for_broadcast_text)

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
    await message.answer(f"📢 <b>Прев'ю:</b>\n\n{message.text}", parse_mode="HTML", reply_markup=kb)
    await state.set_state(AdminStates.confirm_broadcast)

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