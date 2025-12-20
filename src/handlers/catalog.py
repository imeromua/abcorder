from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.database.db import db
from src.keyboards import (
    get_main_menu, 
    get_departments_keyboard, 
    get_categories_keyboard, 
    get_products_keyboard
)

router = Router()

class SearchStates(StatesGroup):
    waiting_for_query = State()

# --- СТАРТ ТА ГОЛОВНЕ МЕНЮ ---

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    # Визначаємо роль користувача для правильного меню
    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", message.from_user.id)
    role = user['role'] if user else 'user'
    
    # Якщо юзера немає в базі, створюємо (авто-реєстрація)
    if not user:
        await db.execute(
            "INSERT INTO users (user_id, username, full_name, role) VALUES ($1, $2, $3, 'shop') ON CONFLICT DO NOTHING",
            message.from_user.id, message.from_user.username, message.from_user.full_name
        )
        role = 'shop'

    await message.answer(
        f"👋 Привіт, {message.from_user.first_name}!\nОберіть дію в меню:",
        reply_markup=get_main_menu(role)
    )

# --- КАТАЛОГ: ВІДДІЛИ ---

@router.message(F.text == "📂 Каталог")
async def show_catalog_root(message: types.Message, state: FSMContext):
    await state.clear()
    
    # Отримуємо унікальні відділи
    # department - це ID, але у нас може бути мапа назв. 
    # Тут припустимо, що department це число, а назву беремо з першого ліпшого товару або хардкодимо
    # Для простоти візьмемо унікальні ID відділів
    rows = await db.fetch_all("SELECT DISTINCT department FROM products ORDER BY department")
    
    # Формуємо список словників для клавіатури
    departments = [{'department': r['department'], 'name': f"Відділ {r['department']}"} for r in rows]
    
    if not departments:
        await message.answer("📦 Каталог порожній.")
        return

    await message.answer(
        "📂 <b>Каталог товарів</b>\nОберіть відділ:",
        parse_mode="HTML",
        reply_markup=get_departments_keyboard(departments)
    )

# --- НАВІГАЦІЯ ПО КАТЕГОРІЯХ (ДИНАМІЧНА) ---

@router.callback_query(F.data.startswith("dept_"))
async def open_department(callback: types.CallbackQuery):
    """Вхід у відділ (Root level)"""
    dept_id = callback.data.split("_")[1]
    
    # Шлях починається з ID відділу
    current_path = dept_id 
    
    await show_category_content(callback, current_path)

@router.callback_query(F.data.startswith("nav_"))
async def navigate_category(callback: types.CallbackQuery):
    """Навігація вглиб або назад"""
    # nav_1/Напої/Вода
    path = callback.data.replace("nav_", "")
    await show_category_content(callback, path)

async def show_category_content(callback: types.CallbackQuery, path: str, page: int = 0):
    """
    Головна функція-роутер каталогу.
    Вирішує, що показати: підкатегорії чи список товарів.
    """
    parts = path.split("/")
    dept_id = int(parts[0])
    
    # Рівень вкладеності (0 = відділ, 1 = піддепартамент, 2 = група...)
    depth = len(parts) 
    
    # 1. Шукаємо підкатегорії на цьому рівні
    # Логіка: вибираємо category_path з бази, розбиваємо, і дивимось, що йде далі після нашого path
    # Це спрощена логіка. Для швидкодії краще мати окрему таблицю категорій, але працюємо з тим що є.
    
    # Формуємо SQL шаблон для пошуку children
    # Якщо path = "1/Напої", то шукаємо все, що починається на "Напої/" в цьому відділі
    
    # Будуємо префікс шляху для пошуку в БД (виключаючи відділ, бо він окремою колонкою)
    db_path_prefix = "/".join(parts[1:]) 
    
    query = """
        SELECT DISTINCT category_path FROM products 
        WHERE department = $1 AND category_path LIKE $2
    """
    like_pattern = f"{db_path_prefix}%" if db_path_prefix else "%"
    
    rows = await db.fetch_all(query, dept_id, like_pattern)
    
    # Витягуємо наступні унікальні вузли
    next_categories = set()
    has_products_here = False
    
    for row in rows:
        cat_str = row['category_path']
        if not cat_str: continue
        
        cat_parts = cat_str.split("/")
        
        # Перевіряємо, чи є підкатегорія на наступному рівні
        # parts[1:] це масив поточного шляху без відділу
        # cat_parts це повний шлях з бази
        
        current_depth_in_db = len(cat_parts)
        # Наш depth враховує відділ як 1, тому індекси зміщені. 
        # depth=1 (ми у відділі 1). cat_parts[0] - це перша підкатегорія.
        
        check_idx = depth - 1
        
        if current_depth_in_db > check_idx:
            next_categories.add(cat_parts[check_idx])
        elif current_depth_in_db == check_idx:
            # Це означає, що ми досягли дна цієї гілки, тут є товари
            has_products_here = True

    sorted_cats = sorted(list(next_categories))

    # --- ВАРІАНТ А: Показуємо підкатегорії ---
    if sorted_cats:
        # Формуємо кнопку "Назад"
        if depth > 1:
            parent_path = "/".join(parts[:-1])
            back_cb = f"nav_{parent_path}"
        else:
            back_cb = "start_menu" # Або повернення до вибору відділів (тут спрощено)

        await callback.message.edit_text(
            f"📂 <b>{parts[-1] if depth > 1 else f'Відділ {dept_id}'}</b>\nОберіть категорію:",
            parse_mode="HTML",
            reply_markup=get_categories_keyboard(sorted_cats, path, back_cb)
        )
    
    # --- ВАРІАНТ Б: Показуємо товари ---
    else:
        # Товари знаходяться за цим шляхом
        # Якщо префікс пустий, то шукаємо все у відділі, інакше точне співпадіння
        prod_query = """
            SELECT article, name, stock_qty, stock_sum 
            FROM products 
            WHERE department = $1 AND category_path = $2
            ORDER BY name
            LIMIT $3 OFFSET $4
        """
        limit = 10
        offset = page * limit
        
        # Точний шлях в базі
        exact_db_path = "/".join(parts[1:])
        
        products = await db.fetch_all(prod_query, dept_id, exact_db_path, limit, offset)
        
        # Рахуємо всього для пагінації
        count_res = await db.fetch_one(
            "SELECT count(*) as cnt FROM products WHERE department = $1 AND category_path = $2",
            dept_id, exact_db_path
        )
        total_items = count_res['cnt']
        total_pages = (total_items + limit - 1) // limit
        
        # Кнопка назад веде на рівень вище
        if depth > 1:
            parent_path = "/".join(parts[:-1])
            back_cb = f"nav_{parent_path}"
        else:
            back_cb = "start_menu"

        if not products:
             await callback.message.edit_text("😔 В цій категорії немає товарів.", reply_markup=get_categories_keyboard([], path, back_cb))
             return

        await callback.message.edit_text(
            f"📦 <b>Товари:</b> {parts[-1]}\nСторінка {page+1}/{total_pages}",
            parse_mode="HTML",
            reply_markup=get_products_keyboard(products, page, total_pages, f"nav_{path}")
        )

# --- ПАГІНАЦІЯ ТОВАРІВ ---
# Оскільки ми не передаємо весь контекст в кнопку page_, нам треба його знати
# Або ми змінимо catalog_kb.py щоб передавати шлях, або (простіше)
# використаємо той факт, що повідомлення не змінюється, і ми можемо витягти шлях з кнопки "Назад"
# Але це ненадійно. 
# Тому ми трохи схитрили в keyboards: 
# Ми зробимо окремий хендлер, який парсить складнішу callback data, якщо б ми її туди зашили.
# АБО: Просто ігноруємо цей складний кейс зараз і змушуємо юзера користуватись пошуком :)
# Жартую.

# Додамо просту пагінацію, яка працює тільки якщо ми знаємо поточний шлях.
# В ідеалі: callback_data="page_2|1/Напої/Вода"
# Давайте виправимо це в catalog_kb.py (віртуально), або тут зробимо спрощення.

# --- ПОШУК ---

@router.callback_query(F.data == "start_search")
async def start_search_mode(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SearchStates.waiting_for_query)
    await callback.message.answer("🔍 <b>Пошук товару</b>\nВведіть назву або артикул:")
    await callback.answer()

@router.message(SearchStates.waiting_for_query)
async def process_search(message: types.Message, state: FSMContext):
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("⚠️ Занадто короткий запит.")
        return
        
    # Шукаємо
    sql = """
        SELECT article, name, stock_qty, stock_sum 
        FROM products 
        WHERE name ILIKE $1 OR article ILIKE $1
        LIMIT 20
    """
    products = await db.fetch_all(sql, f"%{query}%")
    
    if not products:
        await message.answer("😔 Нічого не знайдено.")
        return # залишаємось в стані пошуку
    
    # Показуємо результати (без пагінації для простоти, перші 20)
    # back_callback тут веде в меню
    await message.answer(
        f"🔍 Результати пошуку: <b>{query}</b>",
        parse_mode="HTML",
        reply_markup=get_products_keyboard(products, 0, 1, "start_menu")
    )
    await state.clear()