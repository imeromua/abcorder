import math
from contextlib import suppress
from aiogram import Router, F, types
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from src.database.db import db
from src.keyboards.inline import get_product_keyboard

# Допоміжні білдери клавіатур
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

def build_universal_menu(items, callback_prefix, back_callback):
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(text=str(item['name']), callback_data=f"{callback_prefix}_{item['id']}")
    builder.adjust(2)
    
    if back_callback == "close":
        builder.row(InlineKeyboardButton(text="❌ Закрити", callback_data="close_catalog"))
    else:
        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))
    return builder.as_markup()

# !!! ОНОВЛЕНИЙ БІЛДЕР: Приймає окремо поточне місце і куди йти назад !!!
def build_products_menu(items, current_callback, back_callback):
    builder = InlineKeyboardBuilder()
    for item in items:
        text = f"{item['name']} | {item['price']:.0f} грн"
        # Для товару зберігаємо поточне місце (current_callback), щоб повернутися в цей список
        callback = f"cprod_{item['article']}_{current_callback}"
        builder.button(text=text, callback_data=callback)
    builder.adjust(1)
    
    # А кнопка "Назад" веде на рівень вище (back_callback)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))
    return builder.as_markup()


catalog_router = Router()

# =======================
# 1. ПОШУК (Текстом)
# =======================
@catalog_router.message(F.text & ~F.text.startswith("/") & ~F.text.in_({"📂 Каталог", "🛒 Кошик", "👤 Мій профіль", "📊 Аналітика (ТОП)", "⚙️ Адмінка"}))
async def search_handler(message: types.Message):
    query = message.text.strip()
    sql = "SELECT * FROM products WHERE article = $1 OR name ILIKE $2 LIMIT 10"
    products = await db.fetch_all(sql, query, f"%{query}%")

    if not products:
        await message.answer("🤷‍♂️ Нічого не знайдено.")
        return

    if len(products) > 1:
        text = f"🔍 <b>Знайдено {len(products)} товарів:</b>\n\n"
        for p in products:
            price = 0
            if p['stock_qty'] > 0: price = p['stock_sum'] / p['stock_qty']
            elif p['sales_qty'] > 0: price = p['sales_sum'] / p['sales_qty']
            
            icon = "📦" if p['stock_qty'] > 0 else "⚪️"
            text += f"{icon} <b>{p['name']}</b>\n🆔 <code>{p['article']}</code> | 💰 {price:.2f} грн\n---\n"
        
        kb = InlineKeyboardBuilder()
        kb.button(text="❌ Закрити результати", callback_data="close_catalog")
        await message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())

    elif len(products) == 1:
        await show_product_card(message, products[0], is_edit=False)


# =======================
# 2. НАВІГАЦІЯ (Рівень 0: Відділи)
# =======================
@catalog_router.message(F.text == "📂 Каталог")
async def open_catalog_root(message: types.Message):
    sql = "SELECT DISTINCT department FROM products ORDER BY department"
    rows = await db.fetch_all(sql)
    depts = [{'name': str(r['department']), 'id': str(r['department'])} for r in rows if r['department'] is not None]
    
    if not depts:
        await message.answer("📂 Каталог порожній.")
        return

    await message.answer(
        "📂 <b>Оберіть відділ:</b>", 
        reply_markup=build_universal_menu(depts, "nav", "close"),
        parse_mode="HTML"
    )

@catalog_router.callback_query(F.data == "catalog_root")
async def back_to_root(callback: CallbackQuery):
    sql = "SELECT DISTINCT department FROM products ORDER BY department"
    rows = await db.fetch_all(sql)
    depts = [{'name': str(r['department']), 'id': str(r['department'])} for r in rows if r['department'] is not None]

    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            "📂 <b>Оберіть відділ:</b>", 
            reply_markup=build_universal_menu(depts, "nav", "close"),
            parse_mode="HTML"
        )


# =======================
# 3. НАВІГАЦІЯ (Дерево)
# =======================
@catalog_router.callback_query(F.data.startswith("nav_"))
async def navigate_category(callback: CallbackQuery):
    parts = callback.data.split("_")
    dept_id = parts[1]
    path_indices = parts[2:] if len(parts) > 2 else []
    
    current_path_str = await resolve_path_from_indices(dept_id, path_indices)
    next_depth = len(path_indices) + 1
    
    sql = f"""
        SELECT DISTINCT split_part(category_path, '/', {next_depth}) as item_name
        FROM products 
        WHERE department = $1 
          AND ($2 = '' OR category_path ILIKE $3)
        ORDER BY item_name
    """
    
    rows = await db.fetch_all(sql, int(dept_id), current_path_str, f"{current_path_str}/%")
    items = [r['item_name'] for r in rows if r['item_name']]
    
    # КІНЕЦЬ ГІЛКИ -> ТОВАРИ
    if not items:
        # Передаємо поточний callback як "current", щоб з товарів повернутись сюди
        await show_products_in_category(callback, dept_id, current_path_str, callback.data)
        return

    # ПАПКИ
    menu_items = []
    base_callback = callback.data
    for i, name in enumerate(items):
        menu_items.append({'name': name, 'id': i})

    if not path_indices:
        back_callback = "catalog_root"
    else:
        back_callback = "_".join(parts[:-1])

    title = current_path_str.split('/')[-1] if current_path_str else f"Відділ {dept_id}"

    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"📂 <b>{title}</b>:",
            reply_markup=build_universal_menu(menu_items, base_callback, back_callback),
            parse_mode="HTML"
        )

# --- СПИСОК ТОВАРІВ ---
async def show_products_in_category(callback, dept_id, path_str, current_callback):
    sql = """
        SELECT * FROM products 
        WHERE department = $1 AND category_path ILIKE $2
        ORDER BY sales_sum DESC
        LIMIT 10
    """
    products = await db.fetch_all(sql, int(dept_id), f"{path_str}%")
    
    if not products:
        await callback.answer("Порожня категорія", show_alert=True)
        return

    prod_items = []
    for p in products:
        price = 0
        if p['stock_qty'] > 0: price = p['stock_sum'] / p['stock_qty']
        elif p['sales_qty'] > 0: price = p['sales_sum'] / p['sales_qty']
        
        prod_items.append({
            'name': p['name'], 
            'price': price, 
            'article': p['article']
        })

    # --- ВИЗНАЧЕННЯ КНОПКИ "НАЗАД" ---
    parts = current_callback.split("_")
    # Якщо parts = ['nav', '10'] (ми у відділі), то назад -> catalog_root
    # Якщо parts = ['nav', '10', '0'] (ми в папці), то назад -> nav_10
    if len(parts) <= 2:
        back_callback = "catalog_root"
    else:
        back_callback = "_".join(parts[:-1])

    title = path_str.split('/')[-1] if path_str else f"Відділ {dept_id}"

    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            f"📦 <b>{title}</b> (Топ-10 продажів):",
            # Передаємо ДВА callback-и: де ми є (current) і куди назад (back)
            reply_markup=build_products_menu(prod_items, current_callback, back_callback),
            parse_mode="HTML"
        )

# --- HELPER ---
async def resolve_path_from_indices(dept_id, indices):
    current_path = ""
    for depth, index in enumerate(indices):
        index = int(index)
        sql = f"""
            SELECT DISTINCT split_part(category_path, '/', {depth + 1}) as item_name
            FROM products 
            WHERE department = $1 
              AND ($2 = '' OR category_path ILIKE $3)
            ORDER BY item_name
        """
        rows = await db.fetch_all(sql, int(dept_id), current_path, f"{current_path}/%")
        items = [r['item_name'] for r in rows if r['item_name']]
        
        if index < len(items):
            if current_path: current_path += f"/{items[index]}"
            else: current_path = items[index]
        else: return current_path
    return current_path


# =======================
# 4. КЛІК ПО ТОВАРУ (З КАТАЛОГУ - РЕДАГУВАННЯ)
# =======================
@catalog_router.callback_query(F.data.startswith("cprod_"))
async def show_product_card_edit(callback: CallbackQuery):
    parts = callback.data.split("_")
    article = parts[1]
    # Все, що після cprod_ART_ - це адреса поточного списку (current_callback)
    # Вона і стане адресою повернення (back_callback) для картки
    back_callback = "_".join(parts[2:]) 
    
    p = await db.fetch_one("SELECT * FROM products WHERE article = $1", article)
    if p:
        await show_product_card(callback.message, p, is_edit=True, back_callback=back_callback)
    await callback.answer()


# =======================
# 5. КЛІК ПО ТОВАРУ (З ПОШУКУ - НОВЕ ПОВІДОМЛЕННЯ)
# =======================
@catalog_router.callback_query(F.data.startswith("prod_"))
async def show_product_card_new(callback: CallbackQuery):
    article = callback.data.split("_")[1]
    p = await db.fetch_one("SELECT * FROM products WHERE article = $1", article)
    if p:
        await show_product_card(callback.message, p, is_edit=False)
    await callback.answer()


# =======================
# УНІВЕРСАЛЬНА ФУНКЦІЯ КАРТКИ
# =======================
async def show_product_card(message: types.Message, p: dict, is_edit: bool, back_callback: str = None):
    price = 0.0
    if p['stock_qty'] > 0: price = p['stock_sum'] / p['stock_qty']
    elif p['sales_qty'] > 0: price = p['sales_sum'] / p['sales_qty']
    
    cluster_emoji = {"A": "💎 A", "B": "⚖️ B", "C": "🐢 C"}.get(p['cluster'], "⚪️")

    stock_qty_fmt = math.ceil(p['stock_qty'])
    sales_qty_fmt = int(p['sales_qty'])
    sales_sum_fmt = f"{p['sales_sum']:.2f}"
    stock_sum_fmt = f"{p['stock_sum']:.2f}"

    text = (
        f"📦 <b>{p['name']}</b>\n\n"
        f"💰 <b>Ціна:</b> {price:.2f} грн\n"
        f"📊 <b>Клас:</b> {cluster_emoji}\n"
        f"🆔 <b>Артикул:</b> <code>{p['article']}</code>\n"
        f"🏭 <b>Постачальник:</b> {p['supplier']}\n\n"
        f"📂 <b>Шлях:</b> {p['category_path']}\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"• Продажі: {sales_qty_fmt} шт ({sales_sum_fmt} грн)\n"
        f"• Залишок: {stock_qty_fmt} шт ({stock_sum_fmt} грн)"
    )

    markup = get_product_keyboard(p['article'], back_callback)

    if is_edit:
        with suppress(TelegramBadRequest):
            await message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=markup)


@catalog_router.callback_query(F.data == "close_catalog")
async def close_catalog(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()