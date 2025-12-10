import os

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from src.database.db import db
from src.keyboards.inline import (get_cart_actions_keyboard, get_cart_keyboard,
                                  get_success_add_keyboard)
from src.services.exporter import exporter
from src.states.user_states import OrderStates

cart_router = Router()

# --- 1. ДОДАВАННЯ ТОВАРУ ---

@cart_router.callback_query(F.data.startswith("add_"))
async def start_add_to_cart(callback: types.CallbackQuery, state: FSMContext):
    """Початок додавання товару: запит кількості"""
    article = callback.data.split("_")[1]
    
    product = await db.fetch_one("SELECT * FROM products WHERE article = $1", article)
    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", callback.from_user.id)
    
    if not product:
        await callback.answer("Товар не знайдено", show_alert=True)
        return

    role = user['role']
    limit_text = ""
    max_qty = 999999
    
    # Логіка для магазинів (НЗ = 3)
    if role == 'shop':
        available = int(product['stock_qty']) - 3
        if available < 0: available = 0
        max_qty = available
        limit_text = f"\n⚠️ <b>Доступно для переміщення:</b> {available} шт. (НЗ: 3)"
        
        if available == 0:
            await callback.answer("⛔️ Товар недоступний (Залишок < 3)", show_alert=True)
            return

    await state.update_data(article=article, max_qty=max_qty, role=role, product_name=product['name'])
    await state.set_state(OrderStates.waiting_for_quantity)

    await callback.message.answer(
        f"🔢 Введіть кількість для <b>{product['name']}</b>:{limit_text}",
        reply_markup=get_cart_keyboard(article),
        parse_mode="HTML"
    )
    await callback.answer()


@cart_router.message(OrderStates.waiting_for_quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    """Обробка введеного числа"""
    if not message.text.isdigit():
        await message.answer("❌ Будь ласка, введіть ціле число.")
        return

    qty = int(message.text)
    data = await state.get_data()
    
    article = data['article']
    max_qty = data['max_qty']
    role = data['role']
    product_name = data.get('product_name', 'Товар')

    # Перевірки
    if role == 'shop' and qty > max_qty:
        await message.answer(f"⛔️ Помилка! Максимум для замовлення: {max_qty} шт.")
        return

    if qty <= 0:
        await message.answer("❌ Кількість має бути більше 0.")
        return
    
    if qty > 1000:
         await message.answer(f"🧐 Ви ввели <b>{qty}</b> шт. Це дуже багато. Перевірте.", parse_mode="HTML")

    # Запис у БД (Upsert)
    await db.execute("""
        INSERT INTO cart (user_id, article, quantity)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, article) 
        DO UPDATE SET quantity = cart.quantity + $3
    """, message.from_user.id, article, qty)

    await state.clear()
    
    # Відповідь з кнопкою переходу до кошика
    await message.answer(
        f"✅ <b>Додано в кошик:</b> {product_name} — {qty} шт.", 
        parse_mode="HTML",
        reply_markup=get_success_add_keyboard()
    )


@cart_router.callback_query(F.data == "cancel_order")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    """Скасування додавання"""
    await state.clear()
    await callback.message.delete()
    await callback.answer("Скасовано")


# --- 2. ПЕРЕГЛЯД КОШИКА ---

async def show_cart(message_or_callback, user_id):
    """Універсальна функція показу кошика"""
    # SQL: беремо товари юзера
    sql = """
        SELECT c.article, c.quantity, p.name, p.stock_qty, p.stock_sum, p.sales_qty, p.sales_sum 
        FROM cart c
        JOIN products p ON c.article = p.article
        WHERE c.user_id = $1
        ORDER BY p.name
    """
    items = await db.fetch_all(sql, user_id)
    
    is_callback = isinstance(message_or_callback, types.CallbackQuery)
    message = message_or_callback.message if is_callback else message_or_callback

    if not items:
        text = "🛒 <b>Ваш кошик порожній.</b>\nЗнайдіть товар через пошук і додайте його."
        if is_callback:
            await message.answer(text, parse_mode="HTML") # Краще нове повідомлення, щоб не губилось
        else:
            await message.answer(text, parse_mode="HTML")
        return

    # Формування чека
    text = "🛒 <b>ВАШЕ ЗАМОВЛЕННЯ:</b>\n\n"
    total_items = 0
    total_sum = 0

    for i, item in enumerate(items, 1):
        price = 0
        stock_qty = float(item['stock_qty'])
        sales_qty = float(item['sales_qty'])
        
        # Розрахунок ціни
        if stock_qty > 0:
            price = float(item['stock_sum']) / stock_qty
        elif sales_qty > 0:
            price = float(item['sales_sum']) / sales_qty
            
        qty = item['quantity']
        sum_line = price * qty
        total_sum += sum_line
        total_items += 1

        text += f"<b>{i}. {item['name']}</b>\n"
        text += f"   🆔 <code>{item['article']}</code> | {qty} шт x {price:.2f} грн\n"

    text += f"\n----------------\n"
    text += f"📦 <b>Всього позицій:</b> {total_items}\n"
    text += f"💰 <b>Орієнтовна сума:</b> {total_sum:.2f} грн"

    await message.answer(text, parse_mode="HTML", reply_markup=get_cart_actions_keyboard())


@cart_router.message(Command("cart"))
async def view_cart_command(message: types.Message):
    """Команда /cart"""
    await show_cart(message, message.from_user.id)


@cart_router.callback_query(F.data == "view_cart_btn")
async def view_cart_btn(callback: types.CallbackQuery):
    """Кнопка 'Перейти до кошика'"""
    await show_cart(callback, callback.from_user.id)
    await callback.answer()


# --- 3. КЕРУВАННЯ ЗАМОВЛЕННЯМ ---

@cart_router.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: types.CallbackQuery):
    """Очищення кошика"""
    await db.execute("DELETE FROM cart WHERE user_id = $1", callback.from_user.id)
    await callback.message.edit_text("🗑 <b>Кошик очищено!</b>", parse_mode="HTML")
    await callback.answer("Готово")


@cart_router.callback_query(F.data == "submit_order")
async def submit_order_handler(callback: types.CallbackQuery):
    """Формування файлів та відправка"""
    user_id = callback.from_user.id
    
    # 1. Роль
    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", user_id)
    role = user['role']

    # 2. Товари
    sql = """
        SELECT c.article, c.quantity, p.name, p.department, p.supplier 
        FROM cart c
        JOIN products p ON c.article = p.article
        WHERE c.user_id = $1
    """
    rows = await db.fetch_all(sql, user_id)
    
    if not rows:
        await callback.answer("Кошик порожній!", show_alert=True)
        return

    items = [dict(row) for row in rows]
    await callback.message.answer("⏳ <b>Формую файли замовлення...</b>", parse_mode="HTML")

    try:
        # 3. Експорт
        files = await exporter.generate_order_files(items, role, user_id)
        
        # 4. Звіт
        if role == 'shop':
            summary = f"🚚 <b>Заявка на переміщення готова!</b>\nЗгруповано по {len(files)} відділах."
        else:
            summary = f"🏭 <b>Замовлення постачальникам готові!</b>\nЗгруповано по {len(files)} контрагентах."
            
        await callback.message.answer(summary, parse_mode="HTML")

        # 5. Відправка файлів
        for file_path in files:
            await callback.message.answer_document(FSInputFile(file_path))
            # Видаляємо тимчасовий файл
            try:
                os.remove(file_path)
            except:
                pass
            
        # 6. Фінал
        await db.execute("DELETE FROM cart WHERE user_id = $1", user_id)
        # Видаляємо повідомлення з кнопками, щоб не натиснули ще раз
        await callback.message.delete()
        await callback.message.answer("✅ <b>Кошик очищено.</b> Готовий до нових замовлень!", parse_mode="HTML")

    except Exception as e:
        await callback.message.answer(f"❌ Помилка генерації: {e}")