from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from src.config import config
from src.database.db import db
from src.services.exporter import exporter
from src.services.notifier import notifier
from src.keyboards.cart_kb import (
    get_cart_keyboard, 
    get_success_add_keyboard, 
    get_cart_actions_keyboard,
    get_order_type_keyboard
)

cart_router = Router()

class OrderStates(StatesGroup):
    waiting_for_quantity = State()

# --- ДОДАВАННЯ В КОШИК ---

@cart_router.callback_query(F.data.startswith("add_"))
async def start_add_to_cart(callback: types.CallbackQuery, state: FSMContext):
    """
    Показує розширену картку товару і запитує кількість.
    Підтримує швидкі кнопки додавання.
    """
    parts = callback.data.split("_")
    article = parts[1]
    
    # Зберігаємо callback повернення, якщо він є
    back_cb = None
    if len(parts) > 2 and not parts[2].isdigit():
        back_cb = "_".join(parts[2:])

    # [ЗМІНА 1] Отримуємо більше даних для красивої картки
    prod = await db.fetch_one("""
        SELECT name, stock_qty, stock_sum, supplier, department, cluster 
        FROM products WHERE article = $1
    """, article)
    
    if not prod:
        await callback.answer("Товар не знайдено!", show_alert=True)
        return

    # [ЗМІНА 2] Розрахунок ціни
    price = prod['stock_sum'] / prod['stock_qty'] if prod['stock_qty'] > 0 else 0.0
    
    # Зберігаємо контекст
    await state.update_data(article=article, back_cb=back_cb, max_qty=int(prod['stock_qty']))
    await state.set_state(OrderStates.waiting_for_quantity)

    # [ЗМІНА 3] Красива HTML картка замість сухого тексту
    text = (
        f"🛍 <b>{prod['name']}</b>\n"
        f"🆔 Артикул: <code>{article}</code>\n"
        f"🏭 Постачальник: <i>{prod['supplier'] or 'Не вказано'}</i>\n"
        f"🗂 Група: {prod['cluster'] or '-'}\n\n"
        f"📊 Наявність: <b>{prod['stock_qty']} шт.</b>\n"
        f"💰 Ціна: <b>{price:.2f} грн</b>\n\n"
        "👇 <b>Введіть кількість або оберіть варіант:</b>"
    )
    
    await callback.message.edit_text(
        text, 
        parse_mode="HTML", 
        reply_markup=get_cart_keyboard(article)
    )

@cart_router.callback_query(F.data == "cancel_order")
async def cancel_add(callback: types.CallbackQuery, state: FSMContext):
    """Скасування вводу"""
    await state.clear()
    await callback.message.delete()
    await callback.answer("Скасовано")

# [ЗМІНА 4] Новий хендлер для кнопок +1, +5
@cart_router.callback_query(F.data.startswith("qty_"))
async def quick_quantity_input(callback: types.CallbackQuery, state: FSMContext):
    """Обробляє натискання кнопок з цифрами"""
    qty_str = callback.data.split("_")[1] # qty_5 -> 5
    
    # Емулюємо повідомлення, ніби користувач ввів текст
    message = types.Message(
        message_id=callback.message.message_id,
        date=callback.message.date,
        chat=callback.message.chat,
        from_user=callback.from_user,
        text=qty_str,
        bot=callback.bot
    )
    
    # Викликаємо головну функцію з прапором from_button=True
    await process_quantity(message, state, from_button=True, original_msg=callback.message)

@cart_router.message(OrderStates.waiting_for_quantity)
async def process_quantity(message: types.Message, state: FSMContext, from_button=False, original_msg=None):
    """Обробка кількості (Транзакція)"""
    text = message.text.strip()
    
    if not text.isdigit():
        if not from_button:
            await message.answer("🔢 Введіть ціле число!")
        return

    qty = int(text)
    if qty <= 0:
        if not from_button:
            await message.answer("❌ Кількість > 0!")
        return

    data = await state.get_data()
    article = data.get('article')
    back_cb = data.get('back_cb')
    user_id = message.from_user.id

    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", user_id)
    role = user['role'] if user else 'shop'

    # --- ТРАНЗАКЦІЯ ---
    try:
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                product = await connection.fetchrow(
                    "SELECT name, stock_qty FROM products WHERE article = $1 FOR UPDATE", 
                    article
                )
                
                if not product:
                    await message.answer("❌ Товар зник.")
                    await state.clear()
                    return

                # Перевірка лімітів
                max_qty = 999999
                if role == 'shop':
                    reserve = config.STOCK_RESERVE
                    available = int(product['stock_qty']) - reserve
                    if available < 0: available = 0
                    max_qty = available
                
                max_qty = min(max_qty, config.MAX_ORDER_QTY)

                if qty > max_qty:
                    msg = f"⛔️ Доступно: <b>{max_qty}</b> шт."
                    # [ЗМІНА 5] Якщо це кнопка - редагуємо старе повідомлення, щоб не смітити
                    if from_button:
                        await original_msg.edit_text(
                            original_msg.html_text + f"\n\n{msg}", 
                            parse_mode="HTML", 
                            reply_markup=get_cart_keyboard(article)
                        )
                    else:
                        await message.answer(msg, parse_mode="HTML")
                    return

                # Запис
                await connection.execute("""
                    INSERT INTO cart (user_id, article, quantity)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, article) 
                    DO UPDATE SET quantity = $3, updated_at = CURRENT_TIMESTAMP
                """, user_id, article, qty)

        logger.info(f"🛒 Cart: {user_id} added {qty} of {article}")
        
        success_text = f"✅ <b>{product['name']}</b>\nДодано в кошик: <b>{qty} шт.</b>"
        
        if from_button:
            await original_msg.edit_text(success_text, parse_mode="HTML", reply_markup=get_success_add_keyboard(back_cb))
        else:
            await message.answer(success_text, parse_mode="HTML", reply_markup=get_success_add_keyboard(back_cb))
            
        await state.clear()

    except Exception as e:
        logger.error(f"Cart Error: {e}")
        if not from_button:
            await message.answer("❌ Помилка кошика.")
        await state.clear()

# --- ПЕРЕГЛЯД КОШИКА (Без змін логіки, тільки перевірка) ---

@cart_router.message(F.text == "🛒 Кошик")
@cart_router.callback_query(F.data == "view_cart_btn")
async def show_cart(event: types.Message | types.CallbackQuery):
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

    lines = []
    total_sum = 0
    for item in items:
        price = item['stock_sum'] / item['stock_qty'] if item['stock_qty'] > 0 else 0
        sum_line = price * item['quantity']
        total_sum += sum_line
        lines.append(f"▫️ <b>{item['name']}</b>\n   {item['quantity']} шт. x {price:.2f} = {sum_line:.2f} грн")

    text = f"🛒 <b>Ваше замовлення:</b>\n\n" + "\n".join(lines) + f"\n\n💰 Разом: <b>{total_sum:.2f} грн</b>"
    
    if isinstance(event, types.CallbackQuery):
        await message.edit_text(text, parse_mode="HTML", reply_markup=get_cart_actions_keyboard())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_cart_actions_keyboard())

# --- КЕРУВАННЯ КОШИКОМ ---

@cart_router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery):
    await db.execute("DELETE FROM cart WHERE user_id = $1", callback.from_user.id)
    await callback.answer("Кошик очищено")
    await callback.message.edit_text("🛒 Кошик порожній.")

@cart_router.callback_query(F.data == "submit_order")
async def pre_submit_order(callback: types.CallbackQuery):
    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", callback.from_user.id)
    role = user['role']
    
    if role == 'shop':
        await finalize_order(callback, role, 'department')
    else:
        await callback.message.edit_text(
            "📋 Як сформувати файли замовлення?",
            reply_markup=get_order_type_keyboard()
        )

@cart_router.callback_query(F.data.startswith("order_type_"))
async def admin_select_order_type(callback: types.CallbackQuery):
    mode = 'supplier' if 'supp' in callback.data else 'department'
    await finalize_order(callback, 'admin', mode)

async def finalize_order(callback: types.CallbackQuery, role: str, grouping_mode: str):
    await callback.message.edit_text("⏳ Формую замовлення...")
    user_id = callback.from_user.id
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
        files = await exporter.generate_order_files(items, grouping_mode, user_id)
        await callback.message.delete()
        
        for file_path in files:
            await callback.message.answer_document(
                types.FSInputFile(file_path),
                caption=f"✅ Замовлення сформовано ({grouping_mode})"
            )
            
        user_info = f"{callback.from_user.full_name} (@{callback.from_user.username})"
        await notifier.info(
            callback.bot, 
            f"🛍 <b>Нове замовлення!</b>\n"
            f"Користувач: {user_info}\n"
            f"Позицій: {len(items)}\n"
            f"Режим: {grouping_mode}"
        )

        await db.execute("DELETE FROM cart WHERE user_id = $1", user_id)
        await callback.message.answer("🎉 Дякуємо! Замовлення відправлено.", reply_markup=get_cart_keyboard(''))

    except Exception as e:
        logger.error(f"Order failed: {e}")
        await callback.message.answer(f"❌ Помилка при формуванні замовлення: {e}")