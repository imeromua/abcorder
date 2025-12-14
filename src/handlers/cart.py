import os
import shutil
from email.mime import message

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from src.config import config
from src.database.db import db
from src.keyboards.inline import (get_cart_actions_keyboard, get_cart_keyboard,
                                  get_order_type_keyboard,
                                  get_success_add_keyboard)
from src.phrases import get_random
from src.services.exporter import exporter
from src.services.notifier import notifier
from src.states.user_states import OrderStates

cart_router = Router()

# =======================
# 1. ДОДАВАННЯ ТОВАРУ
# =======================

@cart_router.callback_query(F.data.startswith("add_"))
async def start_add_to_cart(callback: types.CallbackQuery, state: FSMContext):
    """Початок додавання товару"""
    parts = callback.data.split("_")
    article = parts[1]
    back_callback = "_".join(parts[2:]) if len(parts) > 2 else None
    
    product = await db.fetch_one("SELECT * FROM products WHERE article = $1", article)
    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", callback.from_user.id)
    
    if not product:
        await callback.answer("Товар не знайдено (можливо, видалено)", show_alert=True)
        return

    role = user['role']
    limit_text = ""
    max_qty = 999999
    
    # Логіка лімітів для магазинів (Незгораний залишок)
    if role == 'shop':
        reserve = config.STOCK_RESERVE
        available = int(product['stock_qty']) - reserve
        if available < 0: available = 0
        max_qty = available
        
        limit_text = f"\n⚠️ <b>Доступно:</b> {available} шт. (НЗ: {reserve})"
        
        if available == 0:
            await callback.answer(f"⛔️ Товар недоступний (Залишок ≤ {reserve})", show_alert=True)
            return

    await state.update_data(
        article=article, 
        max_qty=max_qty, 
        role=role, 
        product_name=product['name'],
        back_callback=back_callback 
    )
    await state.set_state(OrderStates.waiting_for_quantity)

    await callback.message.answer(
        f"🔢 Введіть кількість для <b>{product['name']}</b>:{limit_text}\n"
        f"<i>(Можна писати формули, напр. 10+5)</i>",
        reply_markup=get_cart_keyboard(article),
        parse_mode="HTML"
    )
    await callback.answer()


@cart_router.message(OrderStates.waiting_for_quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    """Обробка введеного числа (калькулятор)"""
    text = message.text.strip()
    
    # Валідація символів (безпечний eval)
    allowed_chars = set("0123456789+-*/(). ")
    if not set(text).issubset(allowed_chars):
        await message.answer("❌ Введіть коректне число або формулу (напр. <code>10+20</code>)")
        return

    try:
        # Рахуємо вираз
        qty = int(eval(text, {"__builtins__": None}, {}))
    except:
        await message.answer("❌ Помилка в розрахунках. Спробуйте простіше число.")
        return

    data = await state.get_data()
    max_qty = data['max_qty']
    role = data['role']
    product_name = data.get('product_name', 'Товар')
    back_callback = data.get('back_callback')

    # Перевірки
    if role == 'shop' and qty > max_qty:
        await message.answer(f"⛔️ Помилка! Максимум для замовлення: {max_qty} шт.")
        return

    if qty <= 0:
        await message.answer("❌ Кількість має бути більше 0.")
        return
    
    if qty > config.MAX_ORDER_QTY:
         await message.answer(f"🧐 Ви ввели <b>{qty}</b> шт. Це більше ліміту ({config.MAX_ORDER_QTY}). Перевірте.", parse_mode="HTML")
         return

    # Запис у БД (Upsert)
    await db.execute("""
        INSERT INTO cart (user_id, article, quantity)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, article) 
        DO UPDATE SET quantity = cart.quantity + $3
    """, message.from_user.id, data['article'], qty)

    await state.clear()
    
    await message.answer(
        f"✅ <b>Додано в кошик:</b> {product_name} — {qty} шт.", 
        parse_mode="HTML",
        reply_markup=get_success_add_keyboard(back_callback)
    )


@cart_router.callback_query(F.data == "cancel_order")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("Скасовано")


# =======================
# 2. ПЕРЕГЛЯД КОШИКА
# =======================

async def show_cart(message_or_callback, user_id):
    """Універсальна функція показу кошика з розбиттям на повідомлення"""
    sql = """
        SELECT c.article, c.quantity, p.name, p.stock_qty, p.stock_sum 
        FROM cart c
        JOIN products p ON c.article = p.article
        WHERE c.user_id = $1
        ORDER BY p.name
    """
    items = await db.fetch_all(sql, user_id)
    
    is_callback = isinstance(message_or_callback, types.CallbackQuery)
    message = message_or_callback.message if is_callback else message_or_callback

    if not items:
        text = "🛒 <b>Ваш кошик порожній.</b>"
        await message.answer(text, parse_mode="HTML")
        if is_callback: await message_or_callback.answer()
        return

    header = "🛒 <b>ВАШЕ ЗАМОВЛЕННЯ:</b>\n\n"
    total_sum = 0
    
    # Логіка розбиття повідомлень (chunks)
    messages_to_send = []
    current_text = header
    
    for i, item in enumerate(items, 1):
        price = 0
        stock_qty = float(item['stock_qty'])
        if stock_qty > 0:
            price = float(item['stock_sum']) / stock_qty
            
        qty = item['quantity']
        sum_line = price * qty
        total_sum += sum_line

        line = f"<b>{i}. {item['name']}</b>\n"
        line += f"   🆔 <code>{item['article']}</code> | {qty} шт x {price:.2f} грн\n"
        
        # 4000 - безпечний ліміт Telegram
        if len(current_text) + len(line) > 4000:
            messages_to_send.append(current_text)
            current_text = line
        else:
            current_text += line

    footer = f"\n----------------\n📦 <b>Всього позицій:</b> {len(items)}\n💰 <b>Орієнтовна сума:</b> {total_sum:.2f} грн"
    
    if len(current_text) + len(footer) > 4000:
        messages_to_send.append(current_text)
        messages_to_send.append(footer)
    else:
        current_text += footer
        messages_to_send.append(current_text)

    # Відправка
    for i, msg_text in enumerate(messages_to_send):
        # Кнопки тільки на останньому повідомленні
        if i == len(messages_to_send) - 1:
            await message.answer(msg_text, parse_mode="HTML", reply_markup=get_cart_actions_keyboard())
        else:
            await message.answer(msg_text, parse_mode="HTML")
            
    if is_callback: await message_or_callback.answer()


@cart_router.message(Command("cart"))
async def view_cart_command(message: types.Message):
    await show_cart(message, message.from_user.id)

@cart_router.message(F.text == "🛒 Кошик")
async def view_cart_text(message: types.Message):
    await show_cart(message, message.from_user.id)

@cart_router.callback_query(F.data == "view_cart_btn")
async def view_cart_btn(callback: types.CallbackQuery):
    await show_cart(callback, callback.from_user.id)

@cart_router.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: types.CallbackQuery):
    await db.execute("DELETE FROM cart WHERE user_id = $1", callback.from_user.id)
    await callback.message.edit_text("🗑 <b>Кошик очищено!</b>", parse_mode="HTML")
    await callback.answer("Готово")


# =======================
# 3. ФОРМУВАННЯ ЗАМОВЛЕННЯ
# =======================

@cart_router.callback_query(F.data == "submit_order")
async def submit_order_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # Перевірка на пустоту
    check = await db.fetch_one("SELECT count(*) as cnt FROM cart WHERE user_id = $1", user_id)
    if check['cnt'] == 0:
        await callback.answer("Кошик порожній!", show_alert=True)
        return
        
    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", user_id)
    role = user['role']

    # Якщо магазин - зразу по відділах, якщо інші - питаємо
    if role == 'shop':
        await finalize_order(callback, user_id, 'department')
    else:
        await callback.message.answer(
            "📋 <b>Як сформувати замовлення?</b>\nОберіть тип групування:", 
            parse_mode="HTML",
            reply_markup=get_order_type_keyboard()
        )
        await callback.answer()

@cart_router.callback_query(F.data == "order_type_dept")
async def order_by_dept(callback: types.CallbackQuery):
    await finalize_order(callback, callback.from_user.id, 'department')

@cart_router.callback_query(F.data == "order_type_supp")
async def order_by_supp(callback: types.CallbackQuery):
    await finalize_order(callback, callback.from_user.id, 'supplier')

async def finalize_order(callback: types.CallbackQuery, user_id: int, grouping_mode: str):
    """Фіналізація замовлення: генерація, відправка, лог, гумор"""
    sql = """
        SELECT c.article, c.quantity, p.name, p.department, p.supplier 
        FROM cart c
        JOIN products p ON c.article = p.article
        WHERE c.user_id = $1
    """
    rows = await db.fetch_all(sql, user_id)
    items = [dict(row) for row in rows]
    
    msg = await callback.message.answer("⏳ <b>Формую файли...</b>", parse_mode="HTML")
    try: await callback.message.delete(); 
    except: pass

    try:
        # 1. Генерація файлів
        files = await exporter.generate_order_files(items, grouping_mode, user_id)
        
        mode_text = "по відділах" if grouping_mode == 'department' else "по постачальниках"
        
        # 2. Веселе повідомлення
        fun_text = get_random("file_ready")
        summary = f"{fun_text}\n\n📂 Файлів: <b>{len(files)}</b> ({mode_text})"
        await msg.edit_text(summary, parse_mode="HTML")

        # 3. Відправка та архівація
        archive_dir = "data/orders_archive"
        os.makedirs(archive_dir, exist_ok=True)
        
        for file_path in files:
            await callback.message.answer_document(FSInputFile(file_path))
            
            # Переміщуємо в архів
            filename = os.path.basename(file_path)
            destination = os.path.join(archive_dir, filename)
            try:
                shutil.move(file_path, destination)
            except:
                try: os.remove(file_path)
                except: pass
            
        # 4. Очищення бази
        await db.execute("DELETE FROM cart WHERE user_id = $1", user_id)
        
        # 5. АУДИТ (Log to Admin Group)
        try:
            user_info = await db.fetch_one("SELECT full_name, username FROM users WHERE user_id = $1", user_id)
            u_name = user_info['full_name']
            u_nick = f"(@{user_info['username']})" if user_info['username'] else ""
            
            log_text = (
                f"📦 <b>Нове замовлення!</b>\n"
                f"👤 {u_name} {u_nick}\n"
                f"📊 Тип: {mode_text}\n"
                f"📑 Позицій: {len(items)}\n"
                f"📁 Файлів: {len(files)}"
            )
            await notifier.info(callback.bot, log_text)
        except:
            pass # Якщо лог не пройшов - не страшно
            
    except Exception as e:
        # Лог помилки
        await notifier.error(callback.bot, "Order Generation Failed", e)
        
        # Повідомлення юзеру
        error_header = get_random("error_critical")
        await msg.edit_text(f"{error_header}\n\nТехнічні деталі: {e}", parse_mode="HTML")