from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from src.config import config
from src.database.db import db
from src.services.exporter import exporter
from src.services.notifier import notifier
from src.keyboards import (
    get_cart_keyboard, 
    get_success_add_keyboard, 
    get_cart_actions_keyboard,
    get_order_type_keyboard
)

# 🔥 ВИПРАВЛЕНО ІМ'Я РОУТЕРА
cart_router = Router()

class OrderStates(StatesGroup):
    waiting_for_quantity = State()

# --- ДОДАВАННЯ В КОШИК ---

@cart_router.callback_query(F.data.startswith("add_"))
async def start_add_to_cart(callback: types.CallbackQuery, state: FSMContext):
    """Користувач натиснув на товар у каталозі"""
    # data format: add_{article}_{back_callback}
    parts = callback.data.split("_")
    article = parts[1]
    # Збираємо назад шлях для кнопки "Продовжити покупки"
    back_cb = "_".join(parts[2:]) if len(parts) > 2 else None

    # Зберігаємо контекст
    await state.update_data(article=article, back_cb=back_cb)
    await state.set_state(OrderStates.waiting_for_quantity)

    # Отримуємо назву товару для краси
    prod = await db.fetch_one("SELECT name, stock_qty FROM products WHERE article = $1", article)
    if not prod:
        await callback.answer("Товар не знайдено!", show_alert=True)
        return

    text = (
        f"🛒 <b>Додавання в кошик</b>\n"
        f"Товар: {prod['name']}\n"
        f"Доступно: {prod['stock_qty']}\n\n"
        "Введіть кількість (ціле число):"
    )
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_cart_keyboard(article))

@cart_router.callback_query(F.data == "cancel_order")
async def cancel_add(callback: types.CallbackQuery, state: FSMContext):
    """Скасування вводу кількості"""
    await state.clear()
    await callback.message.delete()
    # Можна повертати в меню, але краще просто видалити зайве
    await callback.answer("Скасовано")

@cart_router.message(OrderStates.waiting_for_quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    """Обробка введеного числа (БЕЗПЕЧНА ТРАНЗАКЦІЯ)"""
    text = message.text.strip()
    
    # Перевірка на число
    if not text.isdigit():
        await message.answer("🔢 Будь ласка, введіть коректне ціле число.")
        return

    qty = int(text)
    if qty <= 0:
        await message.answer("❌ Кількість має бути більше 0.")
        return

    data = await state.get_data()
    article = data.get('article')
    back_cb = data.get('back_cb')
    user_id = message.from_user.id

    # Отримуємо роль користувача для перевірки лімітів
    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", user_id)
    role = user['role'] if user else 'shop'

    # 🔥 ПОЧАТОК БЕЗПЕЧНОЇ ЗОНИ (RACE CONDITION FIX) 🔥
    try:
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                # 1. Блокуємо рядок товару (FOR UPDATE)
                product = await connection.fetchrow(
                    "SELECT name, stock_qty FROM products WHERE article = $1 FOR UPDATE", 
                    article
                )
                
                if not product:
                    await message.answer("❌ Товар зник з бази.")
                    await state.clear()
                    return

                # 2. Перевірка залишків (Логіка бізнесу)
                max_qty = 999999
                
                # Якщо це магазин - враховуємо резерв
                if role == 'shop':
                    reserve = config.STOCK_RESERVE
                    available = int(product['stock_qty']) - reserve
                    if available < 0: available = 0
                    max_qty = available
                
                # Обмеження на одне замовлення
                max_qty = min(max_qty, config.MAX_ORDER_QTY)

                # 3. Валідація
                if qty > max_qty:
                    await message.answer(f"⛔️ Доступно для замовлення: <b>{max_qty}</b> шт.", parse_mode="HTML")
                    return

                # 4. Запис у кошик
                await connection.execute("""
                    INSERT INTO cart (user_id, article, quantity)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, article) 
                    DO UPDATE SET quantity = $3, updated_at = CURRENT_TIMESTAMP
                """, user_id, article, qty) 

        # 🔥 КІНЕЦЬ БЕЗПЕЧНОЇ ЗОНИ 🔥
        
        logger.info(f"🛒 Cart Update: User {user_id} set {qty} of {article}")
        
        await message.answer(
            f"✅ <b>{product['name']}</b> ({qty} шт.) у кошику.", 
            parse_mode="HTML",
            reply_markup=get_success_add_keyboard(back_cb)
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Cart Error: {e}")
        await message.answer("❌ Сталася помилка при додаванні товару.")
        await state.clear()

# --- ПЕРЕГЛЯД КОШИКА ---

@cart_router.message(F.text == "🛒 Кошик")
@cart_router.callback_query(F.data == "view_cart_btn")
async def show_cart(event: types.Message | types.CallbackQuery):
    """Показує вміст кошика"""
    # Універсальне отримання message
    message = event.message if isinstance(event, types.CallbackQuery) else event
    user_id = event.from_user.id

    items = await db.fetch_all("""
        SELECT c.article, c.quantity, p.name, p.stock_sum, p.stock_qty
        FROM cart c
        JOIN products p ON c.article = p.article
        WHERE c.user_id = $1
        ORDER BY p.name
    """, user_id)

    if not items:
        text = "🛒 Ваша корзина порожня."
        if isinstance(event, types.CallbackQuery):
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    # Формування чеку
    lines = []
    total_items = 0
    total_sum_approx = 0.0 # Приблизна сума (бо ціна = sum/qty)

    for item in items:
        price = item['stock_sum'] / item['stock_qty'] if item['stock_qty'] > 0 else 0
        sum_line = price * item['quantity']
        total_items += item['quantity']
        total_sum_approx += sum_line
        
        lines.append(f"▫️ <b>{item['name']}</b>\n   {item['quantity']} шт. x {price:.2f} = {sum_line:.2f} грн")

    text = (
        f"🛒 <b>Ваше замовлення:</b>\n\n" + 
        "\n".join(lines) + 
        f"\n\n📦 Всього товарів: <b>{total_items}</b>"
        f"\n💰 Орієнтовна сума: <b>{total_sum_approx:.2f} грн</b>"
    )

    if isinstance(event, types.CallbackQuery):
        await message.edit_text(text, parse_mode="HTML", reply_markup=get_cart_actions_keyboard())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_cart_actions_keyboard())

# --- КЕРУВАННЯ КОШИКОМ ---

@cart_router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery):
    await db.execute("DELETE FROM cart WHERE user_id = $1", callback.from_user.id)
    await callback.answer("🗑 Кошик очищено!")
    await callback.message.edit_text("🛒 Кошик порожній.")

@cart_router.callback_query(F.data == "submit_order")
async def pre_submit_order(callback: types.CallbackQuery):
    """Вибір типу замовлення перед фіналізацією"""
    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", callback.from_user.id)
    role = user['role']

    # Якщо магазин - зразу по відділах
    if role == 'shop':
        await finalize_order(callback, role, 'department')
    else:
        # Адмін може вибрати
        await callback.message.edit_text(
            "📋 Як сформувати файли замовлення?",
            reply_markup=get_order_type_keyboard()
        )

@cart_router.callback_query(F.data.startswith("order_type_"))
async def admin_select_order_type(callback: types.CallbackQuery):
    mode_map = {'dept': 'department', 'supp': 'supplier'}
    mode_key = callback.data.split("_")[2]
    mode = mode_map.get(mode_key, 'department')
    
    await finalize_order(callback, 'admin', mode)

async def finalize_order(callback: types.CallbackQuery, role: str, grouping_mode: str):
    """Генерація файлів та відправка"""
    user_id = callback.from_user.id
    
    await callback.message.edit_text("⏳ Формую замовлення...")
    
    # 1. Отримуємо дані
    items = await db.fetch_all("""
        SELECT c.article, c.quantity, p.name, p.department, p.supplier
        FROM cart c
        JOIN products p ON c.article = p.article
        WHERE c.user_id = $1
    """, user_id)
    
    if not items:
        await callback.message.edit_text("❌ Помилка: кошик порожній.")
        return

    try:
        # 2. Генеруємо файли
        files = await exporter.generate_order_files(items, grouping_mode, user_id)
        
        # 3. Відправляємо користувачу
        await callback.message.delete() # Видаляємо "Формую..."
        
        for file_path in files:
            await callback.message.answer_document(
                types.FSInputFile(file_path),
                caption=f"✅ Замовлення сформовано ({grouping_mode})"
            )
            
        # 4. Сповіщаємо адмінів / групу логування
        user_info = f"{callback.from_user.full_name} (@{callback.from_user.username})"
        await notifier.info(
            callback.bot, 
            f"🛍 <b>Нове замовлення!</b>\n"
            f"Користувач: {user_info}\n"
            f"Позицій: {len(items)}\n"
            f"Режим: {grouping_mode}"
        )

        # 5. Очищаємо кошик
        await db.execute("DELETE FROM cart WHERE user_id = $1", user_id)
        
        await callback.message.answer("🎉 Дякуємо! Замовлення відправлено.", reply_markup=get_cart_keyboard('')) # Або main menu

    except Exception as e:
        logger.error(f"Order failed: {e}")
        await callback.message.answer(f"❌ Помилка при формуванні замовлення: {e}")