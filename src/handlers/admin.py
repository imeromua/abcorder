import os
import shutil
import asyncio
import aiohttp
import re
import zipfile
from datetime import datetime
from aiogram import Router, F, Bot, types
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
    get_dept_export_keyboard,
    get_export_filter_keyboard
)

admin_router = Router()

def transform_drive_url(url: str) -> str:
    """Розумне перетворення посилань: підтримує і файли, і Google Таблиці"""
    # 1. Шукаємо ID файлу. Він завжди йде після '/d/' або як 'id='
    # Цей regex ловить ID і в /file/d/..., і в /spreadsheets/d/...
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url) or \
            re.search(r'id=([a-zA-Z0-9_-]+)', url)
    
    if match:
        file_id = match.group(1)

        # 2. Якщо посилання містить "spreadsheets" — це таблиця
        # Google Таблиці треба експортувати спеціальним url
        if "spreadsheets" in url or "docs.google.com" in url:
             return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"

        # 3. Якщо це звичайний файл на Drive (binary file)
        return f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t&uuid=True"
    
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
    await admin_user_edit(callback)
    
    try:
        await bot.send_message(target_id, f"🔔 Ваші права оновлено! Нова роль: <b>{new_role.upper()}</b>.\nНатисніть /start.", parse_mode="HTML")
    except: pass

@admin_router.callback_query(F.data == "ignore_click")
async def ignore_click(callback: types.CallbackQuery):
    await callback.answer()


# =======================
# 3. МЕНЮ ІМПОРТУ
# =======================
@admin_router.callback_query(F.data == "admin_import_menu")
async def admin_import_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📥 <b>Меню Імпорту</b>\nОберіть спосіб:", 
        parse_mode="HTML", 
        reply_markup=get_import_menu_keyboard()
    )

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
    if not doc.file_name.lower().endswith(('.xlsx', '.csv', '.xlsb', '.zip')):
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
        "🔗 <b>Надішліть посилання (файл/Google Drive):</b>", 
        parse_mode="HTML", 
        reply_markup=get_cancel_import_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_import_link)

@admin_router.message(AdminStates.waiting_for_import_link, F.text)
async def handle_import_link(message: types.Message, state: FSMContext):
    url = transform_drive_url(message.text.strip())
    status = await message.answer("⏳ З'єднуюсь з сервером...")
    
    os.makedirs("data/imports", exist_ok=True)
    path = "data/imports/downloaded_import.xlsx" 
    
    try:
        # User-Agent, щоб прикинутись браузером
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    await status.edit_text(f"❌ Помилка доступу (код {response.status}).")
                    return
                
                ct = response.headers.get("Content-Type", "").lower()
                if "zip" in ct:
                    path = "data/imports/downloaded_import.zip"

                with open(path, 'wb') as f:
                    while True:
                        chunk = await response.content.read(1024*1024)
                        if not chunk: break
                        f.write(chunk)
        
        # --- ПЕРЕВІРКА СИГНАТУРИ ---
        with open(path, 'rb') as f:
            header = f.read(10)
        
        if header.startswith(b'PK'): # Це ZIP або XLSX
            await status.edit_text("✅ Файл отримано. Починаю обробку...")
            await process_import_wrapper(status, path)
        
        elif b'<html' in header.lower() or b'<!doc' in header.lower():
            await status.edit_text(
                "❌ <b>Помилка:</b> Посилання веде на веб-сторінку, а не на файл.\n"
                "Google Drive не віддає файл напряму. Перевірте доступ (Anyone with the link).", 
                parse_mode="HTML"
            )
            try: os.remove(path)
            except: pass
        else:
            await status.edit_text("⚠️ Формат невідомий, пробую як текст/CSV...")
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
    target_file = file_path
    temp_dir = None
    is_zip = False
    
    # Визначаємо, чи це ZIP, але не XLSX
    try:
        if zipfile.is_zipfile(file_path):
            with zipfile.ZipFile(file_path, 'r') as z:
                # XLSX має всередині workbook.xml або [Content_Types].xml
                if 'xl/workbook.xml' not in z.namelist() and '[Content_Types].xml' not in z.namelist():
                    is_zip = True
    except: pass
    
    # Якщо це справжній ZIP - розпаковуємо
    if is_zip or file_path.lower().endswith('.zip'):
        await status_msg.edit_text("🗜 Розпаковую архів...")
        
        temp_dir = os.path.join("data/imports", f"unzip_{datetime.now().strftime('%H%M%S')}")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
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
                await status_msg.edit_text("❌ В архіві не знайдено Excel/CSV.")
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

    await process_import(status_msg, target_file)
    
    if temp_dir:
        try: shutil.rmtree(temp_dir)
        except: pass
    
    if os.path.exists(file_path) and file_path != target_file:
        try: os.remove(file_path)
        except: pass

async def process_import(status_msg: types.Message, file_path: str):
    try:
        await status_msg.edit_text("⚙️ Імпортую дані в базу...")
        count = await importer.import_file(file_path)
        
        success_text = get_random("import_success")
        await status_msg.edit_text(f"{success_text}\n\n📊 Опрацьовано: <b>{count}</b> товарів.", parse_mode="HTML")
        await notifier.info(status_msg.bot, f"📥 <b>Імпорт успішний!</b>\nФайл: {os.path.basename(file_path)}\nКількість: {count}")
        
    except Exception as e:
        await notifier.error(status_msg.bot, f"❌ Помилка імпорту {os.path.basename(file_path)}", e)
        
        error_header = get_random("error_critical")
        err_msg = str(e)
        if "BadZipFile" in err_msg or "cannot be determined" in err_msg:
            err_msg = "Файл пошкоджено або це не Excel (.xlsx)."
            
        await status_msg.edit_text(f"{error_header}\n\nТехнічні деталі:\n<code>{err_msg}</code>", parse_mode="HTML")


# =======================
# 5. ЕКСПОРТ БАЗИ (ОНОВЛЕНО)
# =======================
@admin_router.callback_query(F.data == "admin_export_menu")
async def admin_export_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📤 <b>Експорт бази товарів</b>\n\nОберіть режим:",
        parse_mode="HTML",
        reply_markup=get_export_menu_keyboard()
    )

# КРОК 1: Вибір обсягу (Все або Відділ)

@admin_router.callback_query(F.data == "export_run_full")
async def export_ask_filter_full(callback: types.CallbackQuery, state: FSMContext):
    # Запам'ятовуємо, що хочемо експортувати ВСЕ
    await state.update_data(export_type="full", dept_id=None)
    await ask_filter(callback, state)

@admin_router.callback_query(F.data == "export_select_dept")
async def export_select_dept(callback: types.CallbackQuery):
    # Показуємо список відділів
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
async def export_ask_filter_dept(callback: types.CallbackQuery, state: FSMContext):
    dept_id = int(callback.data.split("_")[-1])
    # Запам'ятовуємо ID відділу
    await state.update_data(export_type="dept", dept_id=dept_id)
    await ask_filter(callback, state)

async def ask_filter(callback: types.CallbackQuery, state: FSMContext):
    """Спільна функція: питає про фільтр"""
    await callback.message.edit_text(
        "🧹 <b>Застосувати фільтр 'мертвих' товарів?</b>\n\n"
        f"Якщо <b>ТАК</b>: будуть вивантажені лише товари, де:\n"
        f"• Продажі ≥ {config.MIN_SALES} <b>АБО</b>\n"
        f"• Залишок ≥ {config.MIN_STOCK}\n\n"
        f"Якщо <b>НІ</b>: буде вивантажено абсолютно все.",
        parse_mode="HTML",
        reply_markup=get_export_filter_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_export_filter)


# КРОК 2: Обробка відповіді (Так/Ні) і запуск

@admin_router.callback_query(AdminStates.waiting_for_export_filter, F.data.in_({"export_filter_yes", "export_filter_no"}))
async def export_execute(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    export_type = data.get("export_type")
    dept_id = data.get("dept_id")
    
    use_filter = (callback.data == "export_filter_yes")
    
    await state.clear()
    
    # Формуємо текст для повідомлення
    mode_text = f"Відділ {dept_id}" if export_type == "dept" else "ВСЯ БАЗА"
    filter_text = " (Тільки активні)" if use_filter else " (Повний дамп)"
    
    await callback.message.edit_text(f"⏳ <b>Вивантажую...</b>\n{mode_text}{filter_text}", parse_mode="HTML")
    
    try:
        # --- БУДУЄМО SQL ЗАПИТ ---
        base_sql = """
            SELECT department, article, name, category_path, supplier, 
                   resident, cluster, sales_qty, sales_sum, stock_qty, stock_sum 
            FROM products
        """
        
        conditions = []
        params = []
        param_counter = 1

        # 1. Умова по відділу
        if export_type == "dept" and dept_id is not None:
            conditions.append(f"department = ${param_counter}")
            params.append(dept_id)
            param_counter += 1
        
        # 2. Умова по фільтру (Sales OR Stock)
        if use_filter:
            # Важливо взяти в дужки OR умову!
            conditions.append(f"(sales_qty >= ${param_counter} OR stock_qty >= ${param_counter+1})")
            params.append(config.MIN_SALES)
            params.append(config.MIN_STOCK)
            param_counter += 2
        
        # Збираємо WHERE
        if conditions:
            base_sql += " WHERE " + " AND ".join(conditions)
        
        # Виконуємо запит
        rows = await db.fetch_all(base_sql, *params)
        
        if not rows:
            await callback.message.edit_text(f"❌ Даних не знайдено.\n({mode_text}{filter_text})")
            return

        # --- ГЕНЕРАЦІЯ ФАЙЛУ ---
        items = [dict(r) for r in rows]
        file_path = await exporter.export_full_base(items, department_filter=dept_id)
        
        # --- АРХІВАЦІЯ (якщо треба) ---
        file_size = os.path.getsize(file_path)
        final_file_path = file_path
        was_zipped = False
        
        if file_size > 19 * 1024 * 1024:
            await callback.message.edit_text(f"📦 Файл великий ({file_size // 1024 // 1024} MB), пакую в ZIP...", parse_mode="HTML")
            zip_path = file_path + ".zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(file_path, os.path.basename(file_path))
            os.remove(file_path)
            final_file_path = zip_path
            was_zipped = True
        
        caption = (
            f"✅ <b>Експорт завершено!</b>\n"
            f"📊 Режим: {mode_text}\n"
            f"🧹 Фільтр: {'Увімкнено' if use_filter else 'Вимкнено'}\n"
            f"📝 Рядків: {len(items)}"
        )
        if was_zipped:
            caption += "\n🗜 <i>Файл стиснуто в архів</i>"

        await callback.message.answer_document(FSInputFile(final_file_path), caption=caption, parse_mode="HTML")
        
        try: os.remove(final_file_path)
        except: pass
        
        await callback.message.answer("Готово", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Меню", callback_data="admin_back_main")]]))
        
    except Exception as e:
        await notifier.error(callback.bot, "Export Error", e)
        await callback.message.answer(f"❌ Помилка експорту: {e}")

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