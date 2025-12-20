import secrets
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

# 🔥 ВИПРАВЛЕНО: Правильна назва роутера для main.py
catalog_router = Router()

class SearchStates(StatesGroup):
    waiting_for_query = State()

# --- PATH REGISTRY (Fix for BUTTON_DATA_INVALID) ---
# Зберігаємо довгі шляхи в пам'яті, а в кнопки даємо короткі ID
PATH_REGISTRY = {}

def get_short_id(full_path: str) -> str:
    """Генерує або повертає існуючий короткий ID для шляху"""
    for k, v in PATH_REGISTRY.items():
        if v == full_path:
            return k
    
    short_id = secrets.token_urlsafe(8)
    PATH_REGISTRY[short_id] = full_path
    return short_id

def resolve_path(short_id: str) -> str:
    """Відновлює повний шлях з короткого ID"""
    return PATH_REGISTRY.get(short_id, short_id)

# --- СТАРТ ТА ГОЛОВНЕ МЕНЮ ---

@catalog_router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", message.from_user.id)
    role = user['role'] if user else 'user'
    
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

@catalog_router.message(F.text == "📂 Каталог")
async def show_catalog_root(message: types.Message, state: FSMContext):
    await state.clear()
    
    rows = await db.fetch_all("SELECT DISTINCT department FROM products ORDER BY department")
    
    departments = [{'department': r['department'], 'name': f"Відділ {r['department']}"} for r in rows]
    
    if not departments:
        await message.answer("📦 Каталог порожній.")
        return

    await message.answer(
        "📂 <b>Каталог товарів</b>\nОберіть відділ:",
        parse_mode="HTML",
        reply_markup=get_departments_keyboard(departments)
    )

# --- НАВІГАЦІЯ ПО КАТЕГОРІЯХ ---

@catalog_router.callback_query(F.data.startswith("dept_"))
async def open_department(callback: types.CallbackQuery):
    """Вхід у відділ (Root level)"""
    dept_id = callback.data.split("_")[1]
    # Root шлях не скорочуємо, він і так короткий
    await show_category_content(callback, dept_id)

@catalog_router.callback_query(F.data.startswith("nav_"))
async def navigate_category(callback: types.CallbackQuery):
    """Навігація вглиб або назад"""
    short_id = callback.data.replace("nav_", "")
    
    # Розшифровуємо шлях
    path = resolve_path(short_id)
    
    if not path:
        await callback.answer("⚠️ Помилка навігації (застаріле меню). Почніть спочатку.", show_alert=True)
        return

    await show_category_content(callback, path)

async def show_category_content(callback: types.CallbackQuery, path: str, page: int = 0):
    parts = path.split("/")
    dept_id = int(parts[0])
    depth = len(parts) 
    
    db_path_prefix = "/".join(parts[1:]) 
    query = """
        SELECT DISTINCT category_path FROM products 
        WHERE department = $1 AND category_path LIKE $2
    """
    like_pattern = f"{db_path_prefix}%" if db_path_prefix else "%"
    
    rows = await db.fetch_all(query, dept_id, like_pattern)
    
    next_categories = set()
    
    for row in rows:
        cat_str = row['category_path']
        if not cat_str: continue
        cat_parts = cat_str.split("/")
        
        current_depth_in_db = len(cat_parts)
        check_idx = depth - 1
        
        if current_depth_in_db > check_idx:
            next_categories.add(cat_parts[check_idx])

    sorted_cats = sorted(list(next_categories))

    # --- ФОРМУВАННЯ КНОПКИ "НАЗАД" ---
    if depth > 1:
        parent_path = "/".join(parts[:-1])
        parent_short = get_short_id(parent_path)
        back_cb = f"nav_{parent_short}"
    else:
        back_cb = "start_menu"

    # --- ВАРІАНТ А: ПІДКАТЕГОРІЇ ---
    if sorted_cats:
        categories_data = []
        for cat_name in sorted_cats:
            full_child_path = f"{path}/{cat_name}"
            short_child = get_short_id(full_child_path)
            categories_data.append({
                'name': cat_name,
                'callback': f"nav_{short_child}"
            })

        await callback.message.edit_text(
            f"📂 <b>{parts[-1] if depth > 1 else f'Відділ {dept_id}'}</b>\nОберіть категорію:",
            parse_mode="HTML",
            reply_markup=get_categories_keyboard(categories_data, back_cb)
        )
    
    # --- ВАРІАНТ Б: ТОВАРИ ---
    else:
        prod_query = """
            SELECT article, name, stock_qty, stock_sum 
            FROM products 
            WHERE department = $1 AND category_path = $2
            ORDER BY name
            LIMIT $3 OFFSET $4
        """
        limit = 10
        offset = page * limit
        exact_db_path = "/".join(parts[1:])
        
        products = await db.fetch_all(prod_query, dept_id, exact_db_path, limit, offset)
        
        count_res = await db.fetch_one(
            "SELECT count(*) as cnt FROM products WHERE department = $1 AND category_path = $2",
            dept_id, exact_db_path
        )
        total_items = count_res['cnt']
        total_pages = (total_items + limit - 1) // limit
        
        if not products:
             await callback.message.edit_text("😔 В цій категорії немає товарів.", reply_markup=get_categories_keyboard([], back_cb))
             return

        await callback.message.edit_text(
            f"📦 <b>Товари:</b> {parts[-1]}\nСторінка {page+1}/{total_pages}",
            parse_mode="HTML",
            reply_markup=get_products_keyboard(products, page, total_pages, back_cb)
        )

# --- ПОШУК ---

@catalog_router.callback_query(F.data == "start_search")
async def start_search_mode(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SearchStates.waiting_for_query)
    await callback.message.answer("🔍 <b>Пошук товару</b>\nВведіть назву або артикул:")
    await callback.answer()

@catalog_router.message(SearchStates.waiting_for_query)
async def process_search(message: types.Message, state: FSMContext):
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("⚠️ Занадто короткий запит.")
        return
        
    sql = """
        SELECT article, name, stock_qty, stock_sum 
        FROM products 
        WHERE name ILIKE $1 OR article ILIKE $1
        LIMIT 20
    """
    products = await db.fetch_all(sql, f"%{query}%")
    
    if not products:
        await message.answer("😔 Нічого не знайдено.")
        return
    
    await message.answer(
        f"🔍 Результати пошуку: <b>{query}</b>",
        parse_mode="HTML",
        reply_markup=get_products_keyboard(products, 0, 1, "start_menu")
    )
    await state.clear()